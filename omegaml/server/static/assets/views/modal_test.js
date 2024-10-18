// usage: http://192.168.1.18:5000/test/modal/modal_test.html?url=/runtime/worker/foo
$(function () {
  var urlParams = new URLSearchParams(window.location.search);
  var modalUrl = urlParams.get("url");
  $("#modal-content").on("show.bs.modal", function (e) {
    var workerId = "foo";
    $.ajax({
      url: modalUrl,
      success: function (data) {
        $("#modal-content .modal-title").text(data.id);
        $("#modal-content .modal-body").html(data);
      },
    });
  });
  $("#modal-content").modal("show");
});
