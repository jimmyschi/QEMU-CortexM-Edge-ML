#include "ml/mnist_model.hpp"
#include "ml/mnist_weights_generated.h"

namespace ml {

MnistFcModel::MnistFcModel() : d1_(g_w1, g_b1), d2_(g_w2, g_b2), d3_(g_w3, g_b3) {}

int MnistFcModel::predict(const float *image) {
  d1_.forward(image, h1_);
  relu_inplace<1, kH1, 1, float>(h1_);

  d2_.forward(h1_, h2_);
  relu_inplace<1, kH2, 1, float>(h2_);

  d3_.forward(h2_, out_);
  return static_cast<int>(argmax<kOut, float>(out_));
}

}  // namespace ml
