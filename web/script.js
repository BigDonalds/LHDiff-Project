// script.js (Replacement for loadSelectedCase)

// --- Define the new renderLines function (Necessary for this to work) ---
function renderLines(linesData, targetElement) {
    targetElement.innerHTML = '';
    
    linesData.forEach((line) => {
        const lineElement = document.createElement('div');
        // Class names must match the status from the API JSON (e.g., 'changed', 'inserted')
        lineElement.className = `diff-line line-status-${line.status}`; 
        
        // Use a space for empty lines to ensure the div renders correctly
        lineElement.textContent = line.content || ' '; 
        
        targetElement.appendChild(lineElement);
    });
}

// ------------------- MODIFIED FUNCTION: loadSelectedCase -------------------
function loadSelectedCase() {
    const caseSelect = document.getElementById("caseSelect");
    const leftSide = document.getElementById("leftSide");
    const rightSide = document.getElementById("rightSide");

    const caseValue = caseSelect.value;
    const caseNumber = caseValue.replace("case", "");
    const paddedNumber = caseNumber.padStart(2, "0");

    // File paths relative to the 'web' directory where script.js is
    const oldFilePath = `cases/case${paddedNumber}_old.txt`;
    const newFilePath = `cases/case${paddedNumber}_new.txt`;

    leftSide.textContent = "Processing diff...";
    rightSide.textContent = "Processing diff...";

    // 1. Fetch content of both files (simulating user input)
    Promise.all([
        fetch(oldFilePath).then(res => res.text()),
        fetch(newFilePath).then(res => res.text())
    ])
    .then(([oldContent, newContent]) => {
        // 2. 🌟 Call the Python backend API 🌟
        // NOTE: This URL (http://127.0.0.1:5000) assumes you are running the Flask server on port 5000.
        return fetch('http://127.0.0.1:5000/api/diff', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                // Send the actual file contents in the request body
                old: oldContent,
                new: newContent
            })
        })
        .then(response => {
            if (!response.ok) {
                // If the server returns a 4xx or 5xx status code
                throw new Error(`API Error: HTTP ${response.status}`);
            }
            // 3. Get the JSON object from the server response
            return response.json(); 
        });
    })
    .then(diffData => {
        // 4. Render the processed data received as JSON
        // diffData will look like: { "old_file": [{}...], "new_file": [{}...] }
        renderLines(diffData.old_file, leftSide);
        renderLines(diffData.new_file, rightSide);
    })
    .catch(error => {
        console.error("Diff process error:", error);
        leftSide.innerHTML = `<p style="color:red; white-space: pre-wrap;">Error getting diff: ${error.message}</p>`;
        rightSide.innerHTML = "";
    });
}

// script.js (ADD THIS BLOCK AT THE END)

document.addEventListener('DOMContentLoaded', (event) => {
    const caseSelect = document.getElementById('caseSelect');
    
    // 1. Initial Load: Run the diff when the page first loads
    loadSelectedCase();

    // 2. Event Listener: Run the diff every time the user changes the selection
    caseSelect.addEventListener('change', loadSelectedCase);
});