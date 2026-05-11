# A.E.R.I.S. — release proguard rules

# MediaPipe & TFLite native interop
-keep class com.google.mediapipe.** { *; }
-keep class org.tensorflow.lite.** { *; }
-dontwarn com.google.mediapipe.**

# Vosk
-keep class org.vosk.** { *; }
-keep class com.sun.jna.** { *; }
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod
-dontwarn java.awt.**

# Hilt / generated
-keep class dagger.hilt.** { *; }

# Room
-keep class androidx.room.** { *; }

# Moshi reflective adapter for Kotlin
-keep class com.squareup.moshi.** { *; }
-keepclassmembers class kotlin.Metadata { *; }
