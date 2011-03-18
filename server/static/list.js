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


$(document).ready(function() {
  $('a.resolve').click(function() {
    var elem = this;
    $.ajax({
      url: this.href,
      success: function() {
        while (elem && elem.tagName != 'TR') {
          elem = elem.parentNode;
        }
        if (elem) {
          $(elem).remove();
        }
      }
    });
    return false;
  });
  $('a.resolveAll').click(function() {
    if (confirm("Are you sure?")) {
      $('a.resolve').click();
    }
    return false;
  });
  $('a.message').click(function() {
    location.href = this.href + location.search;
    return false;
  });
});
