#include <iostream>
#include <calculations.hpp>

int main()
{
    Calculations calc;

    std::cout << "Addition:       " << calc.Addition(3, 4)       << std::endl;
    std::cout << "Subtraction:    " << calc.Subtraction(10, 4)   << std::endl;
    std::cout << "Multiplication: " << calc.Multiplication(3, 4) << std::endl;
    std::cout << "Division:       " << calc.Division(10, 2)      << std::endl;

    Eigen::Matrix3d A, B;
    A << 1,2,3, 4,5,6, 7,8,9;
    B << 9,8,7, 6,5,4, 3,2,1;
    std::cout << "Matrix product:\n" << calc.matrixMultiplication(A, B) << std::endl;

    // Only call get_timestamps() when connected to a real robot:
    // std::cout << calc.get_timestamps("192.168.1.100") << std::endl;

    return 0;
}