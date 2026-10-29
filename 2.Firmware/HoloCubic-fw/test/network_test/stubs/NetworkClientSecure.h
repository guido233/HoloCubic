#pragma once
struct NetworkClientSecure {
    bool trusted = false;
    void useBuiltinCACertBundle() { trusted = true; }
    void setHandshakeTimeout(unsigned long) {}
};
