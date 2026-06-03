#include <iostream>
#include <calculations.hpp>
#include <Eigen/Eigenvalues>

using namespace std;
using namespace Eigen;

double Calculations::Addition(const double &n1, const double &n2)
{return n1+n2;}

double Calculations::Subtraction(const double &n1, const double &n2)
{return n1-n2;}

double Calculations::Multiplication(const double &n1, const double &n2)
{return n1*n2;}

double Calculations::Division(const double &n1, const double &n2)
{
if (n2==0) throw invalid_argument("Cannot divide by zero!");
else return n1/n2;
}

Matrix3d Calculations::matrixMultiplication(Matrix3d mat1, Matrix3d mat2)
{
    return mat1*mat2;
}

