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

    rstContent.split("\n").forEach((line) => {
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
        sections[currentSection].code = codeBlock.join("\n").trim();
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
        sections[currentSection].code = codeBlock.join("\n").trim();
      }
    });

    return sections;
  }

  createDynamicSections(examples) {
    const pillsContainer = this.$("#apiExamples");
    const contentContainer = this.$("#apiExamplesContent");

    pillsContainer.html("");
    contentContainer.html("");

    const languageNames = {
      python: "Python",
      bash: "cURL",
      yaml: "Swagger",
    };

    Object.entries(examples).forEach(
      ([language, { description, code }], index) => {
        const displayName = languageNames[language] || language;
        const id = language === "bash" ? "curl" : language;

        const pill = $('<li class="nav-item">').append(
          `<a class="nav-link ${
            index === 0 ? "active" : ""
          }" id="${id}-tab" data-toggle="pill" href="#${id}" role="tab">${displayName}</a>`
        );
        pillsContainer.append(pill);

        const content = $(`
            <div class="tab-pane fade ${
              index === 0 ? "show active" : ""
            }" id="${id}" role="tabpanel">
            <div class="row">
               <div class="col-6">
                 <p class="description">${description}</p>                    
               </div>
               <div class="col-6">
                <div class="code-example position-relative">
                    <button class="copy-btn">Copy</button>
                    <pre><code class="language-${language}">${code}</code></pre>                   
                </div>
              </div>
            </div>
        `);
        contentContainer.append(content);

        Prism.highlightElement(content.find("code")[0]);
      }
    );

    this.$(".copy-btn").on("click", function () {
      const $btn = $(this);
      const codeText = $btn.siblings("pre").find("code").text();
      const $textarea = $("<textarea>")
        .val(codeText)
        .css({ position: "fixed", opacity: 0 })
        .appendTo("body");
      $textarea.select();
      document.execCommand("copy");
      $btn.text("Copied!");
      $textarea.remove();
      setTimeout(() => $btn.text("Copy"), 2000);
    });
  }

  loadExamples() {
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
