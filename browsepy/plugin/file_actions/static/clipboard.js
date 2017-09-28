(function() {
  if (document.querySelectorAll && document.addEventListener) {
    function every (arr, fnc) {
      for (let i = 0, l=arr.length; i<l; i++) {
        if (!fnc(arr[i], i, arr)) {
          return false;
        }
      }
      return true;
    }
    function event (element, event, callback) {
      var args = Array.prototype.slice.call(arguments, 3);
      element.addEventListener(event, function () {
        var args2 = Array.prototype.slice.call(arguments);
        callback.apply(this, args.concat(args2));
      });
    }
    function form (element) {
      var parent = element.form || element;
      while (parent && parent.tagName !== 'form') {
        parent = parent.parentNode;
      }
      return parent;
    }
    function checkAll (checkbox) {
      checkbox.form
        .querySelectorAll('td input[type=checkbox]')
        .forEach(function (target) {target.checked = checkbox.checked;});
    }
    function checkRow (tr, event) {
      if (!event || !event.target || event.target.type !== 'checkbox') {
        var
          targets = tr.querySelectorAll('td input[type=checkbox]'),
          checked = every(targets, function (target) {return target.checked;});
        targets.forEach(function (target) {target.checked = !checked;});
      }
    }
    function check (checkbox) {
      checkbox.checked = every(
        checkbox.form.querySelectorAll('td input[type=checkbox]'),
        function (checkbox) {return checkbox.checked;});
    }
    document
      .querySelectorAll('form th.select-all-container')
      .forEach(function (container) {
        var checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        container.appendChild(checkbox);
        event(checkbox, 'change', checkAll, checkbox);
        checkbox.form
          .querySelectorAll('td input[type=checkbox]')
          .forEach(function (input) {
            event(input, 'change', check, checkbox);
          });
        checkbox.form
          .querySelectorAll('tbody tr')
          .forEach(function (tr) {
            tr.className += ' clickable';
            event(tr, 'click', checkRow, tr);
          });
      });
  }
}());
