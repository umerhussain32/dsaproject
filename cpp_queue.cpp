#include <iostream>
#include <queue>
#include <string>

using namespace std;

int main() {
    queue<string> q;
    int count = 0;

    // Read total number of prompts from Python stdin
    if (!(cin >> count)) {
        return 0;
    }
    cin.ignore(); // Clear newline character from buffer

    // Step 1: Push all incoming prompts into the C++ queue (q.push)
    for (int i = 0; i < count; i++) {
        string prompt;
        getline(cin, prompt);
        q.push(prompt);
    }

    // Step 2: Read top prompt (q.front) and remove it from queue (q.pop)
    while (!q.empty()) {
        cout << q.front() << endl; // Send prompt output back to Streamlit
        q.pop();                   // Remove front element from queue
    }

    return 0;
}
