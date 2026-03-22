#ifndef MNIST_MODEL_HPP
#define MNIST_MODEL_HPP

#include <stddef.h>

namespace ml {

template <size_t N, typename T = float>
struct Vector {
    T data[N];

    T &operator[](size_t i) { return data[i]; }
    const T &operator[](size_t i) const { return data[i]; }

    Vector<N, T> operator+(const Vector<N, T> &other) const {
        Vector<N, T> out{};
        for (size_t i = 0; i < N; ++i) {
            out[i] = data[i] + other[i];
        }
        return out;
    }
};

template <size_t In, size_t Out, typename T = float>
class DenseLayer {
public:
    DenseLayer(const T *weights, const T *biases) : weights_(weights), biases_(biases) {}

    void forward(const T *input, T *output) const {
        for (size_t o = 0; o < Out; ++o) {
            T acc = biases_[o];
            for (size_t i = 0; i < In; ++i) {
                acc += input[i] * weights_[i * Out + o];
            }
            output[o] = acc;
        }
    }

private:
    const T *weights_;
    const T *biases_;
};

template <size_t H, size_t W, size_t KH, size_t KW, size_t OC, typename T = float>
class Conv2DLayerSingleIn {
public:
    static constexpr size_t OUT_H = H - KH + 1;
    static constexpr size_t OUT_W = W - KW + 1;

    Conv2DLayerSingleIn(const T *kernel, const T *bias) : kernel_(kernel), bias_(bias) {}

    void forward(const T *input, T *output) const {
        for (size_t oc = 0; oc < OC; ++oc) {
            for (size_t y = 0; y < OUT_H; ++y) {
                for (size_t x = 0; x < OUT_W; ++x) {
                    T acc = bias_[oc];
                    for (size_t ky = 0; ky < KH; ++ky) {
                        for (size_t kx = 0; kx < KW; ++kx) {
                            const size_t in_idx = (y + ky) * W + (x + kx);
                            const size_t k_idx = (oc * KH * KW) + (ky * KW + kx);
                            acc += input[in_idx] * kernel_[k_idx];
                        }
                    }
                    const size_t out_idx = oc * (OUT_H * OUT_W) + y * OUT_W + x;
                    output[out_idx] = acc;
                }
            }
        }
    }

private:
    const T *kernel_;
    const T *bias_;
};

template <size_t H, size_t W, size_t C, typename T = float>
void relu_inplace(T *data) {
    constexpr size_t N = H * W * C;
    for (size_t i = 0; i < N; ++i) {
        if (data[i] < static_cast<T>(0)) {
            data[i] = static_cast<T>(0);
        }
    }
}

template <size_t H, size_t W, size_t C, size_t P, typename T = float>
class MaxPool2D {
public:
    static constexpr size_t OUT_H = H / P;
    static constexpr size_t OUT_W = W / P;

    void forward(const T *input, T *output) const {
        for (size_t c = 0; c < C; ++c) {
            for (size_t oy = 0; oy < OUT_H; ++oy) {
                for (size_t ox = 0; ox < OUT_W; ++ox) {
                    T max_v = input[c * H * W + (oy * P) * W + (ox * P)];
                    for (size_t py = 0; py < P; ++py) {
                        for (size_t px = 0; px < P; ++px) {
                            const size_t idx = c * H * W + (oy * P + py) * W + (ox * P + px);
                            if (input[idx] > max_v) {
                                max_v = input[idx];
                            }
                        }
                    }
                    output[c * OUT_H * OUT_W + oy * OUT_W + ox] = max_v;
                }
            }
        }
    }
};

template <size_t N, typename T = float>
size_t argmax(const T *data) {
    size_t best_idx = 0;
    T best_val = data[0];
    for (size_t i = 1; i < N; ++i) {
        if (data[i] > best_val) {
            best_val = data[i];
            best_idx = i;
        }
    }
    return best_idx;
}

class MnistFcModel {
public:
    static constexpr size_t kInput = 784;
    static constexpr size_t kH1 = 40;
    static constexpr size_t kH2 = 20;
    static constexpr size_t kOut = 10;

    MnistFcModel();

    int predict(const float *image);
    float last_logit(size_t i) const { return out_[i]; }

private:
    DenseLayer<kInput, kH1, float> d1_;
    DenseLayer<kH1, kH2, float> d2_;
    DenseLayer<kH2, kOut, float> d3_;

    float h1_[kH1];
    float h2_[kH2];
    float out_[kOut];
};

}  // namespace ml

#endif
