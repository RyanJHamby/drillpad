use std::fmt;
use std::ops::{Add, Index, IndexMut, Mul};

#[derive(Debug, Clone, PartialEq)]
struct Matrix {
    rows: usize,
    cols: usize,
    data: Vec<f64>,
}

impl Matrix {
    fn new(rows: usize, cols: usize, data: Vec<f64>) -> Result<Matrix, MatrixError> {
        let expected = rows * cols;
        if data.len() != expected {
            return Err(MatrixError::BadDataLength { expected, got: data.len() });
        }
        Ok(Matrix { rows, cols, data })
    }

    fn zeros(rows: usize, cols: usize) -> Matrix {
        Matrix { rows, cols, data: vec![0.0; rows * cols] }
    }

    fn identity(n: usize) -> Matrix {
        let mut m = Matrix::zeros(n, n);
        for i in 0..n {
            m.data[i * n + i] = 1.0;
        }
        m
    }

    fn shape(&self) -> (usize, usize) {
        (self.rows, self.cols)
    }

    fn transpose(&self) -> Matrix {
        let mut out = Matrix::zeros(self.cols, self.rows);
        for r in 0..self.rows {
            for c in 0..self.cols {
                out.data[c * self.rows + r] = self.data[r * self.cols + c];
            }
        }
        out
    }

    fn checked_add(&self, rhs: &Matrix) -> Result<Matrix, MatrixError> {
        if self.shape() != rhs.shape() {
            return Err(MatrixError::DimensionMismatch { left: self.shape(), right: rhs.shape() });
        }
        let data = self.data.iter().zip(&rhs.data).map(|(a, b)| a + b).collect();
        Ok(Matrix { rows: self.rows, cols: self.cols, data })
    }

    fn checked_mul(&self, rhs: &Matrix) -> Result<Matrix, MatrixError> {
        if self.cols != rhs.rows {
            return Err(MatrixError::DimensionMismatch { left: self.shape(), right: rhs.shape() });
        }
        let mut out = Matrix::zeros(self.rows, rhs.cols);
        for i in 0..self.rows {
            for k in 0..self.cols {
                let a = self.data[i * self.cols + k];
                for j in 0..rhs.cols {
                    out.data[i * rhs.cols + j] += a * rhs.data[k * rhs.cols + j];
                }
            }
        }
        Ok(out)
    }
}

impl<'a> Add<&'a Matrix> for &'a Matrix {
    type Output = Matrix;
    fn add(self, rhs: &Matrix) -> Matrix {
        self.checked_add(rhs).expect("dimension mismatch in add")
    }
}

impl<'a> Mul<&'a Matrix> for &'a Matrix {
    type Output = Matrix;
    fn mul(self, rhs: &Matrix) -> Matrix {
        self.checked_mul(rhs).expect("dimension mismatch in mul")
    }
}

impl Mul<f64> for &Matrix {
    type Output = Matrix;
    fn mul(self, rhs: f64) -> Matrix {
        Matrix {
            rows: self.rows,
            cols: self.cols,
            data: self.data.iter().map(|x| x * rhs).collect(),
        }
    }
}

impl Index<(usize, usize)> for Matrix {
    type Output = f64;
    fn index(&self, (r, c): (usize, usize)) -> &f64 {
        assert!(r < self.rows && c < self.cols, "index out of bounds");
        &self.data[r * self.cols + c]
    }
}

impl IndexMut<(usize, usize)> for Matrix {
    fn index_mut(&mut self, (r, c): (usize, usize)) -> &mut f64 {
        assert!(r < self.rows && c < self.cols, "index out of bounds");
        &mut self.data[r * self.cols + c]
    }
}

impl fmt::Display for Matrix {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        for r in 0..self.rows {
            if r > 0 {
                write!(f, "\n")?;
            }
            for c in 0..self.cols {
                if c > 0 {
                    write!(f, " ")?;
                }
                write!(f, "{}", self.data[r * self.cols + c])?;
            }
        }
        Ok(())
    }
}
