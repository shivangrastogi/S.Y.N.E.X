package com.shivang.aeris.vision

import android.content.Context
import android.graphics.Bitmap
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.objectdetector.ObjectDetector as MpObjectDetector
import com.google.mediapipe.tasks.vision.objectdetector.ObjectDetectorResult
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * MediaPipe Object Detector wrapper. Uses EfficientDet-Lite0 (~6 MB) bundled
 * in `assets/models/efficientdet_lite0.tflite`. Returns labels ranked by
 * frame-center proximity + area — matches desktop object_detector.py.
 */
@Singleton
class ObjectDetector @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private var detector: MpObjectDetector? = null

    private fun ensure(): MpObjectDetector {
        detector?.let { return it }
        val base = BaseOptions.builder()
            .setModelAssetPath("models/efficientdet_lite0.tflite")
            .build()
        val opts = MpObjectDetector.ObjectDetectorOptions.builder()
            .setBaseOptions(base)
            .setRunningMode(RunningMode.IMAGE)
            .setMaxResults(8)
            .setScoreThreshold(0.4f)
            .build()
        return MpObjectDetector.createFromOptions(context, opts).also { detector = it }
    }

    suspend fun detect(bitmap: Bitmap): List<Detection> = withContext(Dispatchers.Default) {
        val mp = ensure()
        val result: ObjectDetectorResult = mp.detect(BitmapImageBuilder(bitmap).build())
        val cx = bitmap.width / 2f
        val cy = bitmap.height / 2f
        result.detections().mapNotNull { d ->
            val box = d.boundingBox()
            val cat = d.categories().firstOrNull() ?: return@mapNotNull null
            val area = box.width() * box.height()
            val centerDx = (box.centerX() - cx)
            val centerDy = (box.centerY() - cy)
            val centerness = 1f / (1f + kotlin.math.sqrt(centerDx * centerDx + centerDy * centerDy))
            Detection(
                label = cat.categoryName(),
                confidence = cat.score(),
                rank = centerness * area,
            )
        }.sortedByDescending { it.rank }
    }

    fun close() { runCatching { detector?.close() }; detector = null }

    data class Detection(val label: String, val confidence: Float, val rank: Float)
}
