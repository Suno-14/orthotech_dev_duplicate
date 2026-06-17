#include <iostream>
#include <thread>
#include <chrono>
#include <zenoh/api/config.hxx>
#include <zenoh/api/session.hxx>

int main() {
    auto session = zenoh::Session::open(zenoh::Config::create_default());

    auto subscriber = session.declare_subscriber(
        "robot/joint_states",
        [](const zenoh::Sample& sample) {
            std::cout
                << "Received on ["
                << sample.get_keyexpr().as_string_view()
                << "]: "
                << sample.get_payload().as_string()
                << std::endl;
        },
        []() {});

    std::cout << "Listening on [robot/joint_states]..." << std::endl;

    while (true) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    return 0;
}