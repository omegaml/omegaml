import ExperimentView from "../../views/repository/experimentsview.js";

const experimentsview = new ExperimentView({
  el: "#evaluationsView",
  experiments: window.context.experiments,
});
experimentsview.render();
