import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'tokens.dart';

ThemeData aerisTheme() {
  const scheme = ColorScheme.dark(
    surface: C.bg,
    primary: C.cyan,
    onPrimary: C.bg,
    secondary: C.cyanDim,
    error: C.red,
    onSurface: C.text1,
  );
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: scheme,
    scaffoldBackgroundColor: C.bg,
    fontFamily: 'Sora',
    splashFactory: InkSparkle.splashFactory,
    highlightColor: Colors.transparent,
    textTheme: const TextTheme(
      bodyLarge: T.body,
      bodyMedium: T.body,
      bodySmall: T.small,
      titleLarge: T.title,
      titleMedium: T.heading,
    ),
    textSelectionTheme: const TextSelectionThemeData(
      cursorColor: C.cyan,
      selectionColor: Color(0x5538D9FF),
      selectionHandleColor: C.cyan,
    ),
    inputDecorationTheme: InputDecorationTheme(
      isDense: true,
      hintStyle: T.bodyDim.copyWith(color: C.text3),
      border: InputBorder.none,
      enabledBorder: InputBorder.none,
      focusedBorder: InputBorder.none,
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected) ? C.bg : C.text3),
      trackColor: WidgetStateProperty.resolveWith((s) =>
          s.contains(WidgetState.selected) ? C.cyan : C.surfaceHi),
      trackOutlineColor: WidgetStateProperty.resolveWith((s) =>
          s.contains(WidgetState.selected) ? C.cyan : C.hairline),
    ),
    sliderTheme: const SliderThemeData(
      activeTrackColor: C.cyan,
      inactiveTrackColor: C.surfaceHi,
      thumbColor: C.cyanHot,
      overlayColor: Color(0x2238D9FF),
      trackHeight: 2,
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: C.surfaceHi,
      contentTextStyle: T.body.copyWith(fontSize: 14),
      behavior: SnackBarBehavior.floating,
      actionTextColor: C.cyan,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(4),
          side: const BorderSide(color: C.hairline)),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: C.surface,
      titleTextStyle: T.heading,
      contentTextStyle: T.bodyDim,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(4),
          side: const BorderSide(color: C.hairline)),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: C.surface,
      modalBackgroundColor: C.surface,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(6)),
          side: BorderSide(color: C.hairline)),
    ),
    dividerTheme: const DividerThemeData(color: C.hairlineSoft, thickness: 1),
    iconTheme: const IconThemeData(color: C.text2, size: 22),
    pageTransitionsTheme: const PageTransitionsTheme(builders: {
      TargetPlatform.android: FadeForwardsPageTransitionsBuilder(),
    }),
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      systemOverlayStyle: SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.light,
        systemNavigationBarColor: C.bg,
      ),
    ),
  );
}
