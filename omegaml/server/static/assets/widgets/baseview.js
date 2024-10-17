import $ from "../plugins/jquery/js/jquery.module.js";
import { _, Backbone } from "../plugins/backbone/backbone.module.js";

class BaseView extends Backbone.View {
  constructor(options) {
    super(options);
    this.templateUrl = options.templateUrl; // URL of the template file
  }
  // Render the view using the provided data
  render(data) {
    return $.get(this.templateUrl)
      .then((template) => {
        this.$el.html(""); // Clear the view's element
        this.template = _.template(template);
        this.$el.append(this.template(data));
        return this; // Enable method chaining
      })
      .catch((error) => {
        console.error("Error loading template:", error);
      });
  }
}

export default BaseView;
