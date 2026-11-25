# The native code of ONNX Runtime looks its Java classes up by name (JNI), which the code
# shrinker cannot see. Without this rule a release build drops or renames them, and the app
# aborts on the first frame with "ClassNotFoundException: ai.onnxruntime.TensorInfo".
-keep class ai.onnxruntime.** { *; }
