<h1>LH-Diff</h1>

<p>This tool compares different versions of a source file and uses algorithms to analyze where and how code changes. 
The tool performs two main processes when comparing versions:</p>

<ul>
    <li><strong>Line Difference Analysis</strong> – determines which lines were changed, deleted, or inserted between versions.</li>
    <li><strong>Bug Change Analysis</strong> – detects lines that may represent bug fixes or newly introduced bugs.</li>
</ul>

<p>The tool automatically scans the project’s <code>data/</code> directory, locates files following the naming pattern 
<code>name_v1.ext</code>, <code>name_v2.ext</code>, etc., and processes each version pair in order.  
For every comparison, a detailed results file is generated containing the detected changes and bug-related information.</p>


<hr>

<h2>Features</h2>
<ul>
    <li>Detects line mappings between versions</li>
    <li>Identifies line changes, insertions, and deletions</li>
    <li>Supports multi-file batch processing</li>
    <li>Runs bug analysis on all version pairs</li>
    <li>Outputs clear and detailed result files</li>
</ul>

<hr>

<h2>Requirements</h2>

<ul>
    <li>Install Python</li>
    <li>Install pip</li>
    <li>Install dependencies using: pip install -r requirements.txt</li>
</ul>

<hr>

<h2>Project Structure</h2>

<pre><code>data/                 # Input files
results/              # Output files will be generated here
lh_diff/              # Core implementation
main.py               # Entry point which runs everything
requirements.txt
readme.md
</code></pre>

<hr>

<h2>How to Run</h2>

<p>Execute:</p>

<pre><code>python main.py
</code></pre>

<p>The tool will:</p>
<ol>
    <li>Scan the <code>data/</code> directory</li>
    <li>Find versioned pairs (v1 -> v2, v2 -> v3, ...)</li>
    <li>Compare them</li>
    <li>Generate result files inside <code>results/</code></li>
</ol>

<hr>

<h2>Naming Convention</h2>

<p>Files must follow:</p>
<pre><code>&lt;name&gt;_v&lt;number&gt;.&lt;ext&gt;
</code></pre>

<p>Examples:</p>
<ul>
    <li>calculator_v1.txt</li>
    <li>calculator_v2.txt</li>
</ul>

<p>The tool will automatically pair them.</p>

<hr>

<h2>How It Works</h2>

<p>The comparison pipeline includes:</p>
<ol>
    <li>Extract lines from both versions</li>
    <li>Generate similarity candidates (SimHash)</li>
    <li>Match old lines to new lines</li>
    <li>Detect moved, modified, inserted, deleted lines</li>
    <li>Pass that data to and run bug identification</li>
</ol>

<hr>

<h2>Output</h2>

<p>For each version pair, a file will be created in <code>results/</code>:</p>

<pre><code>&lt;testcase&gt;_vX_to_vY_results.txt
</code></pre>

<p>Each result file includes:</p>
<ul>
    <li>Mapping information</li>
    <li>Deleted lines</li>
    <li>Inserted lines</li>
    <li>Bug fixes found</li>
    <li>Bug introductions found</li>
</ul>

<p>Additionally, an <code>evaluation_results.csv</code> file will be generated.  
This file contains the scoring results for 25 predefined test cases based on the provided <code>groundtruth.json</code>.</p>
