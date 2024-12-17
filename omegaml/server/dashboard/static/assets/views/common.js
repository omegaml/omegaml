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
    return (window._flr[endpoint] || "/404")
      .format(params)
      .replace(/\/\//g, "/");
  } catch (error) {
    console.error(`Failed to retrieve URL for endpoint: ${endpoint}`, error);
  }
};
// format option that can replace markdown {variable} with object properties
String.prototype.sformat = function (params) {
  return (
    this
      // First, replace any double braces with a unique placeholder to avoid conflict
      .replace(/{{([^}]+)}}/g, (match, key) => `\uE000${key}\uE001`)
      // Replace single braces with the actual values
      .replace(/{([^}]+)}/g, (match, key) => {
        const keys = key.split(".");
        return keys.reduce(
          (acc, key) => (acc && acc[key] !== undefined ? acc[key] : ""),
          params
        );
      })
      // Finally, restore double-braced keys by replacing the unique placeholder back to single braces
      .replace(/\uE000([^}]+)\uE001/g, "{$1}")
  );
};
// common alert alternative
// - usage: alert("message", "title", "success")
window.alert = (message, title = "", status = "info") => {
  new Notify({
    status,
    title,
    text: message,
  });
};
