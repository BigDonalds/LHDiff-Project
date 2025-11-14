<h1>COMP-3110 Project - Group 26</h1>

<h3>General requirements</h3>
<ol>
    <li>Given two different versions of a file, map which lines of the old file map to which lines in the new file.</li>
    <li>Evaluate the tool you devveloped in (1) using a new dataset (Contribute a new dataset and evaluate your tool using your dataset and the dataset provided to you). The new dataset should contain the line tracking information of 25 different files.</li>
    <li>How can you visualize line mapping information?
    No implementation is needed. The project report (format of the report and instructions for the final submission will be provided) should contain the design of graphical user interfaces that show how to visualize the information.</li>
</ol>

<h3>Bonus requirements</h3>
<ol>
    <li>Can you extend your tool to identify bug introducing changes from bug fix changes? (10%)</li>
</ol>

<h2>Contributing</h2>
<p>Install requirements with <code>pip install -r requirements.txt</code><p>
<p>Python block comments (and <strong>doc-strings</strong>) are handled using <code>''' comment '''</code> notation <strong>after</strong> the method signature, for example:</p>
<pre><code>def superCoolMethod():
    '''
    this is officially recognized documentation \n
    wow spectacular!
    '''
    print(1+2)</code></pre>
<p>and <strong>not</strong> the following:</p>
<pre><code>'''
this NOT officially recognized documentation!!!
'''
def superCoolMethod():
    print(1+2)</code></pre>

<p>nor</p>
<pre><code># this is also NOT officially recognized documentation
def superCoolMethod():
    print(1+2)</code></pre>