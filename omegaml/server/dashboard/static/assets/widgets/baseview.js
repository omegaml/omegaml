import $ from "../plugins/jquery/js/jquery.module.js";
import { _, Backbone } from "../plugins/backbone/backbone.module.js";
/*
 * BaseView class to handle rendering of views
 *
 * This class is a wrapper around Backbone.View that adds a render method
 * to load a template file dynamically, and render it using the provided data.
 *
 * Usage:
 *
 *   class MyView extends BaseView {
 *    constructor(options) {
 *       _.extend(options, {
 *           el: "#container",
 *           templateUrl: "/path/to/template.html"
 *       })
 *       super(options);
 *    }
 *    render(data) {
 *     return super.render(data)
 *     .then(() => {
 *          // Additional rendering logic
 *     });
 *    }
 *
 *   const view = new MyView();
 *   view.render();
 *
 * The render method returns a Promise that resolves when the template is loaded
 * and rendered into the view's element. Thus you can chain the render method
 * by subclassing BaseView and adding additional functionality, as shown above.
 *
 * BaseView automatically triggers events on the view's element, which
 * makes it easy to add custom events. For example, you can trigger a custom
 * event when a button is clicked:
 *
 *    this.trigger('button:clicked', { key: 'value' });
 *
 * and provide a callback in the view's options:
 *
 *   const view = new BaseView({
 *       el: "#container",
 *      events: {
 *        "button:clicked": function(data) {
 *         console.log('Button clicked:', data);
 *      }
 *   });
 *
 */
class BaseView extends Backbone.View {
  constructor(options) {
    super(options);
    this.options = options || {};
    _.defaults(this.options, { context });
    this.templateUrl = options.templateUrl; // URL of the template file
    this.data = options.data || {}; // Data to be used in the template
    this.fieldMap = options.fieldMap || {}; // Map of field IDs to data keys
  }
  // Render the view using the provided data
  render(context) {
    context = context || {};
    _.defaults(
      context,
      this.options.context,
      this.options,
      window.context || {}
    );
    console.debug("Rendering view with context: ", context);
    return $.get(this.templateUrl)
      .then((template) => {
        this.$el.html(""); // Clear the view's element
        this.template = _.template(template);
        this.$el.append(this.template(context));
        this.populateForm(); // Populate the form with data
        return this; // Enable method chaining
      })
      .catch((error) => {
        console.error("Error loading template:", error);
      });
  }
  trigger(event, data) {
    this.$el.trigger(event, data);
    super.trigger(event, data);
  }
  // Unified change handler for all form fields
  onFieldChange(event) {
    const fieldId = event.target.id;
    this.data[fieldId] = event.target.value;
  }
  // Handle form submission
  onSubmit(event) {
    event.preventDefault();
    console.debug("Form submitted with data: ", this.data);
    this.readFormData();
    this.trigger("submit", this.data);
  }
  // Populate the form fields with data from `this.data`
  populateForm() {
    this.data = this.data || {}; // Ensure data is defined
    for (const [id, key] of Object.entries(this.fieldMap)) {
      const el = this.$(`#${id}`);
      if (el.length > 0 && this.data[key] !== undefined) {
        el.val(this.data[key]);
      }
    }
  }
  // Read form data into `this.data` from the form fields
  readFormData() {
    this.data = {}; // reset or keep existing
    for (const [id, key] of Object.entries(this.fieldMap)) {
      const el = this.$(`#${id}`);
      if (el.length > 0) {
        this.data[key] = el.val();
      }
    }
  }
}

export default BaseView;
