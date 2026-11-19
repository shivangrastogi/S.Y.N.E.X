// The brain's contract → what AERIS actually does (lib/brain/llm/bridge.dart).
import 'package:aeris_assistant/brain/llm/bridge.dart';
import 'package:aeris_assistant/brain/memory_search.dart';
import 'package:aeris_assistant/core/models.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> toolCall(String name, Map<String, dynamic> args) => {
      'type': 'tool_call',
      'calls': [
        {'name': name, 'args': args}
      ],
    };

/// The plan the brain's answer turns into (fails the test if it isn't one).
({String tool, Map<String, Object?> args, bool needsApproval}) planFor(Map<String, dynamic> contract,
    {List<Memory> memories = const []}) {
  final action = actionFromContract(contract, memories: memories, now: DateTime(2026, 11, 17, 21, 0));
  expect(action, isA<BrainRunsPlan>(), reason: '$contract → $action');
  final plan = (action as BrainRunsPlan).plan;
  return (tool: plan.tool, args: plan.args, needsApproval: plan.needsApproval);
}

void main() {
  final memories = [
    Memory(id: 'm1', text: 'Meri car B2 parking mein hai', createdAt: DateTime(2026, 11, 1)),
    Memory(id: 'm2', text: 'Gate code 4471 hai', createdAt: DateTime(2026, 11, 2)),
  ];

  group('speaking', () {
    test('reply is spoken, ask is spoken and waits for the answer', () {
      final reply = actionFromContract({'type': 'reply', 'text': 'Main badhiya hoon!'}) as BrainSpeaks;
      expect((reply.text, reply.expectsAnswer), ('Main badhiya hoon!', false));
      final ask = actionFromContract({'type': 'ask', 'text': 'Kisko bhejun?', 'pending': 'send_message'}) as BrainSpeaks;
      expect((ask.text, ask.expectsAnswer), ('Kisko bhejun?', true));
    });

    test('escalate offers a web search and asks first', () {
      final plan = planFor({'type': 'escalate', 'reason': 'live_info', 'query': 'aaj Pune mein baarish hogi?'});
      expect(plan.tool, 'search');
      expect(plan.args, {'q': 'aaj Pune mein baarish hogi?', 'reason': 'live_info'});
      expect(plan.needsApproval, isTrue);
    });
  });

  group('tools this app runs', () {
    test('alarm: the spoken time becomes a clock time', () {
      final plan = planFor(toolCall('set_alarm', {'time': 'kal subah 7 baje'}));
      expect(plan.tool, 'alarm');
      expect((plan.args['hour'], plan.args['minute']), (7, 0));
    });

    test('alarm without a usable time asks instead of guessing', () {
      expect(planFor(toolCall('set_alarm', {'time': 'jaldi'})).args, {'for': 'alarm'});
    });

    test('timer, torch, battery, time, date, maths', () {
      expect(planFor(toolCall('set_timer', {'duration': '10 minute'})).args, {'seconds': 600});
      expect(planFor(toolCall('flashlight', {'state': 'off'})).args, {'on': false});
      expect(planFor(toolCall('battery_status', {})).tool, 'battery');
      expect(planFor(toolCall('date_time', {'what': 'time'})).tool, 'time');
      expect(planFor(toolCall('date_time', {'what': 'day'})).tool, 'date');
      expect(planFor(toolCall('calculate', {'expression': '12 * 8'})).args['value'], 96);
    });

    test('messages always need approval; app defaults to SMS like the router', () {
      final whatsapp = planFor(toolCall('send_message', {'message': 'late hoon', 'contact': 'Ravi', 'app': 'whatsapp'}));
      expect(whatsapp.args, {'to': 'Ravi', 'body': 'late hoon', 'app': 'whatsapp'});
      expect(whatsapp.needsApproval, isTrue);
      expect(planFor(toolCall('send_message', {'message': 'hi', 'number': '9876543210'})).args['app'], 'sms');
    });

    test('call by name or number; missing callee asks', () {
      expect(planFor(toolCall('call', {'contact': 'Mummy'})).args, {'to': 'Mummy'});
      expect(planFor(toolCall('call', {'number': '9876543210'})).args, {'to': '9876543210'});
    });

    test('open app resolves known packages', () {
      final plan = planFor(toolCall('open_app', {'app': 'YouTube'}));
      expect(plan.args, {'app': 'youtube', 'target': 'com.google.android.youtube'});
    });

    test('remember and recall use the memory store', () {
      expect(planFor(toolCall('remember', {'fact': 'meri car B2 mein hai'})).args, {'text': 'meri car B2 mein hai'});
      expect(planFor(toolCall('recall', {'query': 'car kahan hai'}), memories: memories).args,
          {'id': 'm1', 'text': 'Meri car B2 parking mein hai'});
      // never told → text null → "you haven't told me that yet"
      expect(planFor(toolCall('recall', {'query': 'passport number'}), memories: memories).args['text'], isNull);
    });
  });

  test('tools this app cannot run yet say so instead of doing something wrong', () {
    for (final contract in [
      toolCall('brightness', {'level': 80}),
      toolCall('call', {'contact': 'Ravi', 'app': 'whatsapp'}),
      toolCall('send_message', {'message': 'hi', 'contact': 'Ravi', 'app': 'telegram'}),
      {'type': 'plan', 'goal': 'image to Ravi', 'steps': ['open Gemini', 'send it']},
    ]) {
      expect(actionFromContract(contract), isA<BrainCannotDoYet>(), reason: '$contract');
    }
  });

  test('memory search ranks by shared words and ignores filler', () {
    expect(matchingMemories('gate ka code kya hai', memories).map((m) => m.id), ['m2']);
    expect(matchingMemories('kya hai', memories), isEmpty);
  });
}
