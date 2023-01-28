import BaseView from "./baseview.js";

class CodeExplain extends BaseView {
  constructor(options) {
    _.defaults(options, {
      events: {},
      templateUrl: url_for("static", {
        filename: "/assets/widgets/codeexplain.html",
      }),
      title: "Select Date Range",
      description: "Please select a start and end date.",
    });
    super(options);
    var that = this;
    this.render().then(function () {
      that.loadExamples();
    });
  }

  parseRSTExamples(rstContent) {
    const sections = {};
    let currentSection = null;
    let description = [];
    let codeBlock = [];
    let isCode = false;

    // Helper function to remove the minimum indentation from all lines in the code block
    function normalizeIndentation(code) {
      const lines = code.split("\n");
      const indentLength = Math.min(
        ...lines
          .filter((line) => line.trim())
          .map((line) => line.match(/^ */)[0].length)
      );
      return lines.map((line) => line.slice(indentLength)).join("\n");
    }

    rstContent.split("\n").forEach((line) => {
      line = line.sformat({ segment: segment, metadata: metadata });
      if (line.startsWith(".. code-block::")) {
        isCode = true;
        currentSection = line.split("::")[1].trim();
        sections[currentSection] = {
          description: description.join("\n").trim(),
          code: "",
        };
        description = [];
        codeBlock = [];
      } else if (isCode && line.trim() === "" && codeBlock.length > 0) {
        sections[currentSection].code = normalizeIndentation(
          codeBlock.join("\n")
        );
        currentSection = null;
        codeBlock = [];
        isCode = false;
      } else if (isCode) {
        codeBlock.push(line);
      } else if (!isCode && line.trim() !== "") {
        description.push(line);
      } else if (!isCode && line.trim() === "") {
        description.push("");
      }
      // Store any remaining code block
      if (currentSection && codeBlock.length > 0) {
        sections[currentSection].code = normalizeIndentation(
          codeBlock.join("\n")
        );
      }
    });

    return sections;
  }

  createDynamicSections(examples) {
    const descriptionContainer = document.querySelector("#descriptionContent");
    const pillsContainer = document.querySelector("#apiExamples");
    const contentContainer = document.querySelector("#apiExamplesContent");

    // Clear existing content
    descriptionContainer.innerHTML = "";
    pillsContainer.innerHTML = "";
    contentContainer.innerHTML = "";

    // Language display names
    const languageNames = {
      python: "Python",
      bash: "Bash",
      curl: "cURL",
      yaml: "Swagger",
    };
    const PrismLanguages = {
      python: "python",
      curl: "bash",
      yaml: "yaml",
      bash: "bash",
    };

    // Loop through examples, adding descriptions on the left and code tabs on the right
    Object.entries(examples).forEach(([language, content], index) => {
      const displayName = languageNames[language] || language;
      const prismLanguage = PrismLanguages[language] || language;
      const id = `${prismLanguage}-${index}`;

      // Description Section (Left Column)
      const descriptionSection = document.createElement("div");
      const description =
        content.description ||
        `Explains how to use ${displayName} to work with ${metadata.name}`;
      descriptionSection.className = "mb-4";
      descriptionSection.innerHTML = `
            <h6>${displayName}</h6>
            <p>${description}</p>
        `;
      descriptionContainer.appendChild(descriptionSection);

      // Nav Pill (Right Column)
      const pill = document.createElement("li");
      pill.className = "nav-item";
      pill.innerHTML = `
            <a class="nav-link ${index === 0 ? "active" : ""}" 
               id="${id}-tab" 
               data-toggle="pill" 
               href="#${id}" 
               role="tab">
                ${displayName}
            </a>
        `;
      pillsContainer.appendChild(pill);

      // Code Content Tab
      const codeContent = document.createElement("div");
      codeContent.className = `tab-pane fade ${
        index === 0 ? "show active" : ""
      }`;
      codeContent.id = id;
      codeContent.setAttribute("role", "tabpanel");
      codeContent.innerHTML = `
            <div class="code-example position-relative">
                <button class="copy-btn">Copy</button>
                <pre><code class="language-${prismLanguage}">${content.code}</code></pre>
            </div>
        `;
      contentContainer.appendChild(codeContent);

      // Highlight code
      Prism.highlightElement(codeContent.querySelector("code"));
    });

    // Add copy button functionality for each code block
    $(".copy-btn").on("click", function () {
      const $btn = $(this);
      const $code = $btn.siblings("pre").find("code");

      // Get original unformatted code by removing Prism's formatting
      const $temp = $("<div>").html($code.html());
      const codeText = $code.text();

      // Create temporary textarea for copying
      const $textarea = $("<textarea>")
        .val(codeText)
        .css({
          position: "fixed",
          opacity: 0,
          top: 0,
          left: 0,
        })
        .appendTo("body");

      try {
        // Get the text from the textarea
        const textToCopy = $textarea.val(); // Assuming $textarea is a jQuery object

        // Use the Clipboard API to copy the text
        navigator.clipboard
          .writeText(textToCopy)
          .then(() => {
            $btn.text("Copied");
          })
          .catch((err) => {
            console.error("Failed to copy:", err);
            $btn.text("Failed!");
          });
      } catch (err) {
        console.error("Failed to copy:", err);
        $btn.text("Failed!");
      } finally {
        // Clean up
        $textarea.remove();
        setTimeout(() => {
          $btn.text("Copy");
        }, 2000);
      }
    });
  }

  loadExamples() {
    $.ajax({
      url:
        url_for("omega-server.explain", {
          segment: segment,
        }) +
        "?name=" +
        metadata.name,
      type: "GET",
    }).done((data) => {
      const examples = this.parseRSTExamples(data);
      this.createDynamicSections(examples);
    });
    return;
    const rstContent = `

Foo

.. code-block:: python

  import requests
  # Set the API key and model ID
  API_KEY = "your_api_key_here"
  MODEL_ID = "model_123"
  # prepare request  
  response = requests.post(
      "https://api.mlops.example.com/v1/models/predict",
      headers={
          "Authorization": f"Bearer {API_KEY}",
          "Content-Type": "application/json"
      },
      json={
          "model_id": MODEL_ID,
          "data": {
              "feature1": 0.5,
              "feature2": "category_a"
          }
      }
  )
  # Get the prediction 
  prediction = response.json()
  print(prediction)


cURL Example
------------

some curl text

.. code-block:: bash

  curl -X POST \\
    https://api.mlops.example.com/v1/models/predict \\
    -H "Authorization: Bearer your_api_key_here" \\
    -H "Content-Type: application/json" \\
    -d '{
      "model_id": "model_123",
      "data": {
        "feature1": 0.5,
        "feature2": "category_a"
      }
    }'


Swagger Example
---------------

some swagger text

.. code-block:: yaml

  paths:
    /v1/models/predict:
      post:
        summary: Make a prediction using the model
        parameters:
          - in: header
            name: Authorization
            required: true
            schema:
              type: string
            description: Bearer token authentication
        requestBody:
          required: true
          content:
            application/json:
              schema:
                type: object
                properties:
                  model_id:
                    type: string
                  data:
                    type: object
        responses:
          '200':
            description: Successful prediction
            content:
              application/json:
                schema:
                  type: object
                  `;

    const examples = this.parseRSTExamples(rstContent + "\n");
    this.createDynamicSections(examples);
  }
}

export default CodeExplain;
