import CodeExplain from "../widgets/codeexplain.js";

$(function () {
  $("#explain-tab").on("shown.bs.tab", function (e) {
    console.debug("loading code explain widget");
    new CodeExplain({
      el: "#explain",
    });
  });
});
