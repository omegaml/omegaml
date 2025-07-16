import ExperimentView from "../../views/runtime/experimentsview.js";

const experimentsview = new ExperimentView({
  el: "#evaluationsView",
  experiments: window.context.experiments,
});
experimentsview.render();
