// Lock and dim an area while a request runs, and show the pressed button turning, with a text of what is done.
export function busy(button, text, area) {
  const shown = Array.from(button.childNodes);
  const turning = document.createElement("span");
  turning.className = "spinner-border spinner-border-sm me-1";
  turning.setAttribute("aria-hidden", "true");
  const said = document.createTextNode(text);
  button.replaceChildren(turning, said);
  area.inert = true;
  area.classList.add("busy");
  area.setAttribute("aria-busy", "true");
  return {
    say: function (next) {
      said.textContent = next;
    },
    done: function () {
      button.replaceChildren(...shown);
      area.inert = false;
      area.classList.remove("busy");
      area.removeAttribute("aria-busy");
    },
  };
}
