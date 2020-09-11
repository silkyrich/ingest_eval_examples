/*
 * This is a temporary file to expose the current theme on splunk. Once the function is
 * exposed via Splunk Enterprise, we will remove and replace it.
 */
define([], function () {

    var defaultTheme = 'light';

    var getCurrentTheme = function() {
      return window.__splunk_page_theme__ || defaultTheme;
    };

    return {
      getCurrentTheme: getCurrentTheme
    };
});
