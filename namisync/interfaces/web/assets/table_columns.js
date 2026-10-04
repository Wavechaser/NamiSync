export function createTableColumns(grid, headerCells, columnNames, columnMinimums, filenameIndex, donorIndex) {
  const resizers = headerCells.slice(0, -1).map(
    (cell) => cell.querySelector(".nami-file-list__column-resizer"),
  );
  let columnWidths = null;
  let finishResize = null;

  function minimumWidth(index) {
    return columnMinimums[index] * parseFloat(getComputedStyle(document.documentElement).fontSize);
  }

  function applyColumnWidths() {
    if (columnWidths === null) return;
    for (const [index, name] of columnNames.entries()) {
      if (index === filenameIndex) continue;
      grid.style.setProperty(`--nami-file-column-${name}`, `${columnWidths[index].toFixed(3)}px`);
    }
    grid.dataset.columnsFrozen = "true";
  }

  function refreshResizers() {
    const donorWidth = columnWidths?.[donorIndex] ?? headerCells[donorIndex].getBoundingClientRect().width;
    for (const resizer of resizers) {
      const index = Number(resizer.dataset.columnIndex);
      const currentWidth = headerCells[index].getBoundingClientRect().width;
      resizer.ariaValueMin = String(Math.round(minimumWidth(index)));
      resizer.ariaValueMax = String(Math.round(currentWidth + Math.max(0, donorWidth - minimumWidth(donorIndex))));
      resizer.ariaValueNow = String(Math.round(currentWidth));
    }
  }

  function freezeColumns() {
    if (columnWidths !== null) return;
    const widths = headerCells.map((cell) => cell.getBoundingClientRect().width);
    if (!widths.every((width) => width > 0)) return;
    columnWidths = widths;
    applyColumnWidths();
  }

  function resizeColumn(index, requestedDelta, startWidths, startNameWidth) {
    const minimumDelta = index === filenameIndex
      ? minimumWidth(filenameIndex) - startNameWidth
      : minimumWidth(index) - startWidths[index];
    const maximumDelta = startWidths[donorIndex] - minimumWidth(donorIndex);
    const delta = Math.max(minimumDelta, Math.min(maximumDelta, requestedDelta));
    columnWidths = [...startWidths];
    if (index !== filenameIndex) columnWidths[index] += delta;
    columnWidths[donorIndex] -= delta;
    applyColumnWidths();
    refreshResizers();
  }

  for (const resizer of resizers) {
    const index = Number(resizer.dataset.columnIndex);
    resizer.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      freezeColumns();
      if (columnWidths === null) return;
      const startX = event.clientX;
      const startWidths = [...columnWidths];
      const startNameWidth = headerCells[filenameIndex].getBoundingClientRect().width;
      const move = (moveEvent) => resizeColumn(
        index, moveEvent.clientX - startX, startWidths, startNameWidth,
      );
      finishResize?.();
      finishResize = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", finishResize);
        finishResize = null;
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", finishResize);
    });
    resizer.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      freezeColumns();
      if (columnWidths === null) return;
      resizeColumn(index, event.key === "ArrowRight" ? 8 : -8,
        [...columnWidths], headerCells[filenameIndex].getBoundingClientRect().width);
    });
  }
  return Object.freeze({ freeze: freezeColumns, refresh: refreshResizers, dispose: () => finishResize?.() });
}
