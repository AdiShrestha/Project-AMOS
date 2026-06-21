#include "include/klstream/core/event.hpp"
#include "include/klstream/feature/types.hpp"
using namespace klstream;
int main() {
    Event<FeatureBatch> a, b;
    a = b;
    return 0;
}
