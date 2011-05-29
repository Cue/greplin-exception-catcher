/*
 * Copyright 2011 The greplin-exception-catcher Authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

var urlParams = {};
(function () {
    var e,
        a = /\+/g,  // Regex for replacing addition symbol with a space
        r = /([^&;=]+)=?([^&;]*)/g,
        d = function (s) { return decodeURIComponent(s.replace(a, " ")); },
        q = window.location.search.substring(1);

    while (e = r.exec(q))
       urlParams[d(e[1])] = d(e[2]);
})();


$.ajaxSetup({
  'cache': false,
  'error': function(e, err) {
    alert(err);
  }
});


$(document).ready(function() {
  $('.filter').click(function() {
    var parts = this.innerHTML.split(':', 1);
    delete urlParams[parts[0]];
    delete urlParams.page;
    updateRequest();
  });
  $('a.environment').click(function() {
    urlParams.environment = this.innerHTML;
    delete urlParams.page;
    updateRequest();
    return false;
  });
  $('a.errorLevel').click(function() {
    urlParams.errorLevel = this.innerHTML;
    delete urlParams.page;
    updateRequest();
    return false;
  });
  $('a.project').click(function() {
    urlParams.project = this.innerHTML;
    delete urlParams.page;
    updateRequest();
    return false;
  });
  $('a.server').click(function() {
    urlParams.server = this.innerHTML;
    delete urlParams.page;
    updateRequest();
    return false;
  });
  $('a.next').click(function() {
    urlParams.page = (parseInt(urlParams.page) || 0) + 1;
    updateRequest();
    return false;
  });
  $('.timeago').timeago();
});


function updateRequest() {
  var result = [];
  for (var key in urlParams) {
    result.push(encodeURIComponent(key) + '=' + encodeURIComponent(urlParams[key]));
  }
  var queryString = result.length ? '?' + result.join('&') : '';
  location.href = location.pathname + queryString;
}
