/**
 * AssistantFormView - A Backbone.js View for managing the assistant configuration form.
 *
 * This view handles user interaction with the assistant form fields, manages internal state,
 * and processes the form submission without relying on a Backbone Model. All form data is stored
 * in the `this.data` dictionary.
 *
 * Expected HTML structure includes inputs and selects with the following IDs:
 * - #assistantName
 * - #modelSelect
 * - #systemPrompt
 * - #promptTemplate
 * - #documentSelect
 * - #pipelineSelect
 * - #assistantForm (form element)
 *
 * Options:
 * @param {Object} options - Configuration options.
 * @param {string} [options.modelName] - Initial model name (e.g., LLM type).
 * @param {string|HTMLElement} [options.el] - DOM element or selector for the form.
 *
 * Usage:
 * const view = new AssistantFormView({ modelName: 'demo', el: '#assistantForm' });
 * view.render();
 */
import BaseView from "./baseview.js";

class AssistantFormView extends BaseView {
  constructor(options) {
    _.defaults(options, {
      events: {},
      templateUrl: url_for("static", {
        filename: "/assets/widgets/promptedit.html",
      }),
      el: "#assistantForm",
    });
    // DOM events
    _.extend(options.events, {
      "submit #assistantForm": "onSubmit",
      "change #assistantName": "onFieldChange",
      "change #modelSelect": "onFieldChange",
      "change #systemPrompt": "onFieldChange",
      "change #promptTemplate": "onFieldChange",
      "change #documentSelect": "onFieldChange",
      "change #pipelineSelect": "onFieldChange",
      "change #toolSelect": "onFieldChange",
    });
    super(options);
    this.fieldMap = {
      assistantName: "name",
      modelSelect: "model",
      systemPrompt: "prompt",
      promptTemplate: "template",
      documentSelect: "documents",
      pipelineSelect: "pipeline",
      toolSelect: "tools",
    };
  }
  render(context) {
    super.render(context).then(() => {
      // Initialize Choices.js for select elements
      const choices = new window.Choices($("#toolSelect")[0], {
        searchEnabled: true,
        searchChoices: true,
        removeItems: true,
        removeItemButton: true,
      });
    });
  }
}

export default AssistantFormView;
