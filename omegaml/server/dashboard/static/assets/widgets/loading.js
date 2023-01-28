// Counter for active AJAX requests
let activeRequests = 0;
// Setup AJAX interceptor
$(document)
  .ajaxSend(function () {
    activeRequests++;
    showLoading();
  })
  .ajaxComplete(function (event, xhr, settings) {
    activeRequests--;
    if (activeRequests === 0) {
      hideLoading();
    }
    if (xhr.status !== 200) {
      // Check if the response status is not OK
      let errorMessage = "Loading a resource failed. Please try again later.";
      // Try to get a more specific error message from the response
      try {
        const response = JSON.parse(xhr.responseText);
        errorMessage = response.message || response.error || errorMessage; // Use the message if available
      } catch (e) {
        // If parsing fails, use the default error message
      }
      if (isNotificationVisible(errorMessage)) {
        console.debug("Notification already visible:", errorMessage);
        return; // Exit if the message is already visible
      }
      new Notify({
        status: "error",
        title: "An error has occured",
        text: errorMessage,
      });
    }
  });

function showLoading() {
  $("#loading-indicator").fadeIn();
  $("#loading-bar").css("width", "90%");
}

function hideLoading() {
  $("#loading-bar").css("width", "100%");
  setTimeout(() => {
    $("#loading-bar").css("transition", "none");
    $("#loading-bar").css("width", "0%");
    setTimeout(() => {
      $("#loading-bar").css("transition", "width 0.3s ease");
    }, 50);
  }, 300);
  $("#loading-indicator").fadeOut();
}

function isNotificationVisible(message) {
  // Check if any notification with the same message is currently in the DOM
  const notifications = document.querySelectorAll(
    ".sn-notifications-container"
  );
  for (let notification of notifications) {
    if (notification.textContent.includes(message)) {
      return true; // Notification is already visible
    }
  }
  return false; // No matching notification found
}
