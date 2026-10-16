// While the platform answers, an area is locked and dimmed, and the button pressed turns and says what is
// done.
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
