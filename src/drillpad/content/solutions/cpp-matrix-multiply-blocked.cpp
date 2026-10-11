void matmul_ikj(const double* A, const double* B, double* C, std::size_t m, std::size_t k, std::size_t n) {
    std::fill(C, C + m * n, 0.0);
    for (std::size_t i = 0; i < m; i++) {
        double* c_row = C + i * n;
        for (std::size_t p = 0; p < k; p++) {
            const double a = A[i * k + p];
            const double* b_row = B + p * n;
            for (std::size_t j = 0; j < n; j++) c_row[j] += a * b_row[j];   // unit stride, vectorizable
        }
    }
}

void matmul_blocked(const double* A, const double* B, double* C, std::size_t m, std::size_t k, std::size_t n,
                    std::size_t block = 64) {
    if (block == 0) throw std::invalid_argument("block must be positive");
    std::fill(C, C + m * n, 0.0);
    for (std::size_t ii = 0; ii < m; ii += block) {
        const std::size_t i_end = std::min(ii + block, m);
        for (std::size_t pp = 0; pp < k; pp += block) {
            const std::size_t p_end = std::min(pp + block, k);
            for (std::size_t jj = 0; jj < n; jj += block) {
                const std::size_t j_end = std::min(jj + block, n);
                // One tile of C accumulates the product of a tile of A and a tile of B.
                for (std::size_t i = ii; i < i_end; i++)
                    for (std::size_t p = pp; p < p_end; p++) {
                        const double a = A[i * k + p];
                        for (std::size_t j = jj; j < j_end; j++) C[i * n + j] += a * B[p * n + j];
                    }
            }
        }
    }
}
