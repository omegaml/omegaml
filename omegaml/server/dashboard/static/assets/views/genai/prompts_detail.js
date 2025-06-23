import AssistantFormView from "../../widgets/promptedit.js";

$(function () {
  // Initialize the assistant form view
  const assistantFormView = new AssistantFormView({
    el: "#assistantForm",
    data: window.context.data,
    availableModels: window.context.availableModels || [],
    isNew: window.context.isNew || false,
  });
  assistantFormView.render();
  assistantFormView.on("submit", function (data) {
    $.ajax({
      url: url_for(".prompts_api_save_prompt", {
        name: data.assistantName || data.name,
      }),
      type: "POST",
      contentType: "application/json",
      data: JSON.stringify(data),
      success: function (response) {
        alert("saved");
        window.location = url_for(".prompts_view_detail", {
          name: response.name,
        });
      },
      error: function (xhr) {
        alert(
          "error saving prompt Status" + xhr.status + ": " + xhr.statusText
        );
      },
    });
  });
});
