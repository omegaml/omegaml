String.prototype.format = function () {
  //https://stackoverflow.com/a/73001721/890242
  let str = this.toString();
  if (!arguments.length) {
    return;
  }
  const [args] = arguments;
  for (const key of Object.keys(args)) {
    str = str.replaceAll(`{${key}}`, args[key]);
  }
  return str;
};
// add uri path to base URL
// - gurantees a single slash between base and path
// Usage: "http://example.com".uri("path/to/resource")
// returns: "http://example.com/path/to/resource"
String.prototype.uri = function (path) {
  path = path.substring(0, 1) === "/" ? path.substring(1) : path;
  return this + (this.endsWith("/") ? "" : "/") + path;
};
// provide a URL for a Flask endpoint
// -- requires a global _flr object with endpoint URLs
// -- see omegaml.server.util:js_routes()
window.url_for = (endpoint, params = {}) => {
  try {
    return (window._flr[endpoint] || "#").format(params);
  } catch (error) {
    console.error(`Failed to retrieve URL for endpoint: ${endpoint}`, error);
  }
};
