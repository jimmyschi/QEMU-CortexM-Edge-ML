#include "ml/mnist_model.hpp"
#include "ml/mnist_weights_generated.h"

namespace ml {

MnistCnnModel::MnistCnnModel() : conv_(g_conv_w, g_conv_b), fc_(g_fc_w, g_fc_b) {}

int MnistCnnModel::predict(const float *image) {
  conv_.forward(image, conv_out_);
  relu_inplace<kConvOutH, kConvOutW, kConvOc, float>(conv_out_);

  pool_.forward_nhwc_flat(conv_out_, pool_out_);
  fc_.forward(pool_out_, out_);
  return static_cast<int>(argmax<kOut, float>(out_));
}

}  // namespace ml
