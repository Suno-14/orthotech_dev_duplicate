#include <iostream>
#include <string>
#include <thread>
#include <chrono>
// #include <zenoh/api/config.hxx>
#include <zenoh.hxx>

int main() {
    auto session = zenoh::Session::open(zenoh::Config::create_default());
    auto publisher = session.declare_publisher("robot/joint_states");

    for (int i = 0; i < 5; i++) {
        std::string msg = "joint_states: [1.0, 2.0, 3.0] count=" + std::to_string(i);
        publisher.put(msg);
        std::cout << "Published: " << msg << std::endl;
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    std::cout << "Publisher done." << std::endl;
    return 0;
}
