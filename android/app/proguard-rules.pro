# Retrofit + Moshi
-keepattributes Signature
-keepattributes *Annotation*
-keep class com.dynoip.app.data.model.** { *; }
-keep class com.squareup.moshi.** { *; }
-keepclassmembers class * {
    @com.squareup.moshi.Json <fields>;
}
-dontwarn okhttp3.internal.platform.**
-dontwarn org.bouncycastle.**
-dontwarn org.conscrypt.**
-dontwarn org.openjsse.**
