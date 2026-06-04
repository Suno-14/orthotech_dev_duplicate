#include <iostream>
#include <calculations.hpp>
#include <Eigen/Eigenvalues>
// #include <ur_rtde/rtde_control_interface.h>
#include <ur_rtde/rtde_receive_interface.h>
// #include <ur_rtde/rtde_io_interface.h>

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
    {return mat1*mat2;}

double Calculations::get_timestamps(const string &robot_ip)
    {   ur_rtde::RTDEReceiveInterface rtde_r(robot_ip);
        return rtde_r.getTimestamp();}


