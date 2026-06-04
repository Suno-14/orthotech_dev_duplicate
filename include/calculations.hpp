#ifndef CALCULATIONS_HPP
#define CALCULATIONS_HPP

#include <Eigen/Eigenvalues>
#include <ur_rtde/rtde_receive_interface.h>

using namespace Eigen;
class Calculations
{
public:
    double Addition(const double &a, const double &b);
    double Subtraction(const double &a, const double &b);
    double Multiplication(const double &a, const double &b);
    double Division(const double &a, const double &b);
    Matrix3d matrixMultiplication(Matrix3d mat1, Matrix3d mat2);
    double get_timestamps(const string &robot_ip);
};

#endif