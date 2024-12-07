import CodeExplain from "../widgets/codeexplain.js";

$("#explain-tab").on("shown.bs.tab", function (e) {
  new CodeExplain({
    el: "#explain",
  });
});
