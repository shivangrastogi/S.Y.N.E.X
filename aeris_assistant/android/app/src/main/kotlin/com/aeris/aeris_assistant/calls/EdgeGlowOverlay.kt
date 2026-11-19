package com.aeris.aeris_assistant.calls

import android.animation.ValueAnimator
import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PathMeasure
import android.graphics.PixelFormat
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.SweepGradient
import android.os.Build
import android.provider.Settings
import android.view.RoundedCorner
import android.view.View
import android.view.WindowInsets
import android.view.WindowManager
import android.view.animation.DecelerateInterpolator
import kotlin.math.PI
import kotlin.math.min
import kotlin.math.sin

/** What the glow is showing. Mirrors `GlowState` in lib/calls/call_bridge.dart. */
enum class GlowState { LISTENING, SPEAKING, ACCEPTED, DECLINED }

/**
 * Light flowing around the screen edges while AERIS handles a call — drawn
 * over every app, never over the user's touches.
 *
 * Touch rule (Android 12+): touches pass through another app's overlay only
 * if the overlay window is at most 80 % opaque, so the window alpha is 0.8 and
 * the phone's own Accept / Reject buttons keep working underneath.
 */
object EdgeGlowOverlay {
    private var glowView: EdgeGlowView? = null

    fun canDraw(context: Context) = Settings.canDrawOverlays(context)

    fun show(context: Context, state: GlowState) {
        if (!canDraw(context)) return
        val view = glowView ?: createView(context) ?: return
        view.setState(state)
    }

    fun setLevel(level: Float) {
        glowView?.micLevel = level.coerceIn(0f, 1f)
    }

    /** Fades out, then removes the window. */
    fun hide(context: Context) {
        val view = glowView ?: return
        view.fadeOut { removeView(context, view) }
    }

    fun hideNow(context: Context) {
        glowView?.let { removeView(context, it) }
    }

    private fun createView(context: Context): EdgeGlowView? {
        val appContext = context.applicationContext
        val view = EdgeGlowView(appContext)
        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            else @Suppress("DEPRECATION") WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
                WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
            PixelFormat.TRANSLUCENT,
        ).apply {
            alpha = 0.8f // the touch-pass-through limit, see the class comment
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                fitInsetsTypes = 0 // cover the status and navigation bars too
                layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
            } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
            }
        }
        return try {
            appContext.getSystemService(WindowManager::class.java).addView(view, params)
            glowView = view
            view
        } catch (e: Exception) {
            null
        }
    }

    private fun removeView(context: Context, view: EdgeGlowView) {
        if (glowView === view) glowView = null
        try {
            context.applicationContext.getSystemService(WindowManager::class.java).removeView(view)
        } catch (_: Exception) {
        }
    }
}

/**
 * The glow itself. Two half-outlines start at the bottom centre and run up
 * each side to the top centre, so the entrance can "draw" both sides upwards
 * at once. Painted as layered strokes (wide + faint → thin + bright) with a
 * slowly rotating sweep gradient, plus a bright comet travelling up each side.
 */
@SuppressLint("ViewConstructor")
class EdgeGlowView(context: Context) : View(context) {

    private companion object {
        val AURORA = intArrayOf(
            Color.parseColor("#38D9FF"), // AERIS cyan
            Color.parseColor("#3A7BFF"), // blue
            Color.parseColor("#8B5CF6"), // violet
            Color.parseColor("#5EE6B5"), // mint
            Color.parseColor("#38D9FF"),
        )
        val ACCEPTED = Color.parseColor("#5EE6B5")
        val DECLINED = Color.parseColor("#FF4D5E")

        /** Stroke layers: width in dp and opacity, from the outer haze to the bright core. */
        val LAYERS = listOf(46f to 0.07f, 28f to 0.15f, 15f to 0.30f, 7f to 0.55f, 2.5f to 1f)

        const val ROTATION_SECONDS = 6f // one full turn of the colours
        const val COMET_SECONDS = 2.6f // a comet's trip from bottom to top
    }

    private val density = resources.displayMetrics.density
    private val strokePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val cometPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val cometShader = RadialGradient(
        0f, 0f, 1f, intArrayOf(Color.WHITE, Color.argb(0, 255, 255, 255)), null, Shader.TileMode.CLAMP,
    )
    private val shaderMatrix = Matrix()
    private var auroraShader: SweepGradient? = null

    private val leftHalf = Path()
    private val rightHalf = Path()
    private val leftMeasure = PathMeasure()
    private val rightMeasure = PathMeasure()
    private val revealedPath = Path()
    private val cometPosition = FloatArray(2)
    private var cornerRadius = 40f * density

    private var state = GlowState.SPEAKING
    private val startTime = System.nanoTime()

    /** 0 → 1 as both sides draw upwards when the glow appears. */
    private var reveal = 0f
    /** Overall opacity, faded on exit. */
    private var fade = 1f
    /** 0 = aurora colours, 1 = the accepted/declined colour. */
    private var outcomeMix = 0f
    private var outcomeColor = ACCEPTED

    /** Microphone level 0..1 from Dart; smoothed so the glow breathes instead of flickering. */
    var micLevel = 0f
    private var smoothedLevel = 0f

    init {
        ValueAnimator.ofFloat(0f, 1f).apply {
            duration = 650
            interpolator = DecelerateInterpolator(2f)
            addUpdateListener { reveal = it.animatedValue as Float }
            start()
        }
    }

    fun setState(newState: GlowState) {
        state = newState
        if (newState == GlowState.ACCEPTED || newState == GlowState.DECLINED) {
            outcomeColor = if (newState == GlowState.ACCEPTED) ACCEPTED else DECLINED
            ValueAnimator.ofFloat(outcomeMix, 1f).apply {
                duration = 280
                addUpdateListener { outcomeMix = it.animatedValue as Float }
                start()
            }
        } else {
            outcomeMix = 0f
        }
        postInvalidateOnAnimation()
    }

    fun fadeOut(onDone: () -> Unit) {
        ValueAnimator.ofFloat(fade, 0f).apply {
            duration = 450
            addUpdateListener { fade = it.animatedValue as Float }
            doOnEnd(onDone)
            start()
        }
    }

    override fun onApplyWindowInsets(insets: WindowInsets): WindowInsets {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            insets.getRoundedCorner(RoundedCorner.POSITION_BOTTOM_LEFT)?.let {
                cornerRadius = it.radius.toFloat()
                buildOutline(width, height)
            }
        }
        return super.onApplyWindowInsets(insets)
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) = buildOutline(w, h)

    /** The screen outline, matching the display's rounded corners, as two halves. */
    private fun buildOutline(w: Int, h: Int) {
        if (w == 0 || h == 0) return
        val width = w.toFloat()
        val height = h.toFloat()
        val radius = min(cornerRadius, min(width, height) / 2)
        fun corner(cx: Float, cy: Float) = RectF(cx - radius, cy - radius, cx + radius, cy + radius)

        rightHalf.reset()
        rightHalf.moveTo(width / 2, height)
        rightHalf.lineTo(width - radius, height)
        rightHalf.arcTo(corner(width - radius, height - radius), 90f, -90f, false)
        rightHalf.lineTo(width, radius)
        rightHalf.arcTo(corner(width - radius, radius), 0f, -90f, false)
        rightHalf.lineTo(width / 2, 0f)

        leftHalf.reset()
        leftHalf.moveTo(width / 2, height)
        leftHalf.lineTo(radius, height)
        leftHalf.arcTo(corner(radius, height - radius), 90f, 90f, false)
        leftHalf.lineTo(0f, radius)
        leftHalf.arcTo(corner(radius, radius), 180f, 90f, false)
        leftHalf.lineTo(width / 2, 0f)

        leftMeasure.setPath(leftHalf, false)
        rightMeasure.setPath(rightHalf, false)
        auroraShader = SweepGradient(width / 2, height / 2, AURORA, null)
    }

    override fun onDraw(canvas: Canvas) {
        val shader = auroraShader ?: return
        val seconds = (System.nanoTime() - startTime) / 1e9f

        smoothedLevel += (micLevel - smoothedLevel) * 0.18f
        val intensity = fade * when (state) {
            GlowState.LISTENING -> 0.55f + 0.45f * smoothedLevel
            GlowState.SPEAKING -> 0.72f + 0.28f * sin(2f * PI.toFloat() * 1.1f * seconds)
            GlowState.ACCEPTED, GlowState.DECLINED -> 1f
        }
        val thickness = when (state) {
            GlowState.LISTENING -> 0.85f + 0.45f * smoothedLevel
            else -> 1f
        }

        shaderMatrix.setRotate(360f * seconds / ROTATION_SECONDS, width / 2f, height / 2f)
        shader.setLocalMatrix(shaderMatrix)

        for ((layerDp, layerAlpha) in LAYERS) {
            strokePaint.strokeWidth = layerDp * density * thickness
            // aurora colours, cross-faded into the outcome colour after answer / reject
            strokePaint.shader = shader
            strokePaint.alpha = (255 * layerAlpha * intensity * (1 - outcomeMix)).toInt()
            drawRevealed(canvas, strokePaint)
            if (outcomeMix > 0f) {
                strokePaint.shader = null
                strokePaint.color = outcomeColor
                strokePaint.alpha = (255 * layerAlpha * intensity * outcomeMix).toInt()
                drawRevealed(canvas, strokePaint)
            }
        }
        if (reveal >= 1f && outcomeMix == 0f) drawComets(canvas, seconds, intensity)
        if (fade > 0f) postInvalidateOnAnimation()
    }

    private fun drawRevealed(canvas: Canvas, paint: Paint) {
        for (measure in arrayOf(leftMeasure, rightMeasure)) {
            revealedPath.reset()
            measure.getSegment(0f, measure.length * reveal, revealedPath, true)
            canvas.drawPath(revealedPath, paint)
        }
    }

    /** A bright point running up each side, in step, like light filling a tube. */
    private fun drawComets(canvas: Canvas, seconds: Float, intensity: Float) {
        val progress = (seconds % COMET_SECONDS) / COMET_SECONDS
        val cometRadius = 26f * density * (0.8f + 0.4f * smoothedLevel)
        cometPaint.shader = cometShader
        cometPaint.alpha = (200 * intensity * sin(PI.toFloat() * progress)).toInt() // fades in and out
        for (measure in arrayOf(leftMeasure, rightMeasure)) {
            measure.getPosTan(measure.length * progress, cometPosition, null)
            shaderMatrix.setScale(cometRadius, cometRadius)
            shaderMatrix.postTranslate(cometPosition[0], cometPosition[1])
            cometShader.setLocalMatrix(shaderMatrix)
            canvas.drawCircle(cometPosition[0], cometPosition[1], cometRadius, cometPaint)
        }
    }

    private fun ValueAnimator.doOnEnd(action: () -> Unit) = addListener(object : android.animation.AnimatorListenerAdapter() {
        override fun onAnimationEnd(animation: android.animation.Animator) = action()
    })
}
