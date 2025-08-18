# ===============================================================
# Файл: bot/utils/plotting.py (НОВЫЙ ФАЙЛ)
# Описание: Содержит функции для генерации изображений и графиков
# с использованием matplotlib.
# ===============================================================

import io
import logging

import matplotlib.pyplot as plt
import matplotlib

# Отключаем "шумные" debug-логи от matplotlib
logging.getLogger("matplotlib").setLevel(logging.WARNING)

# --- Константы для стилизации графика ---
# Цвета для градиента от "Страха" (красный) к "Жадности" (зеленый)
GAUGE_COLORS: list[str] = ["#d94b4b", "#e88452", "#ece36a", "#b7d968", "#73c269"]
FIGURE_SIZE: tuple[float, float] = (8, 4.5)
FONT_COLOR: str = "white"
ARROW_COLOR: str = "white"
VALUE_FONT_SIZE: int = 48
CLASSIFICATION_FONT_SIZE: int = 20
DPI: int = 150


def generate_fng_image(value: int, classification: str) -> bytes:
    """
    Генерирует изображение "Индекса страха и жадности" в виде спидометра.

    :param value: Значение индекса (от 0 до 100).
    :param classification: Текстовая классификация (например, "Extreme Fear").
    :return: Изображение в формате PNG как байтовая строка.
    """
    fig = None  # Инициализируем переменную
    try:
        # Используем бэкенд, который не требует GUI
        matplotlib.use("Agg")
        plt.style.use("dark_background")

        # Создаем фигуру и полярные оси
        fig, ax = plt.subplots(figsize=FIGURE_SIZE, subplot_kw={"projection": "polar"})

        # Убираем все лишние элементы (сетку, метки, рамку)
        ax.set_yticklabels([])
        ax.set_xticklabels([])
        ax.grid(False)
        ax.spines["polar"].set_visible(False)
        ax.set_ylim(0, 1)

        # Рисуем цветные сегменты спидометра (от 0 до 100)
        # pi радиан = 180 градусов. Мы рисуем полукруг.
        # 3.14159... это 180 градусов. Мы начинаем справа и идем налево.
        pi = 3.14159
        for i in range(100):
            color_index = min(len(GAUGE_COLORS) - 1, int(i / (100 / len(GAUGE_COLORS))))
            ax.barh(
                1,  # Радиус
                width=pi / 100,  # Ширина одного сегмента
                left=pi - (i * (pi / 100)),  # Позиция
                height=0.3,  # Высота сегмента
                color=GAUGE_COLORS[color_index],
            )

        # Рисуем стрелку-указатель
        angle = pi - (value * (pi / 100))
        ax.annotate(
            "",
            xy=(angle, 1),
            xytext=(0, 0),
            arrowprops=dict(facecolor=ARROW_COLOR, shrink=0.05, width=4, headwidth=10),
        )

        # Добавляем текст в центр фигуры
        fig.text(
            0.5,
            0.5,
            f"{value}",
            ha="center",
            va="center",
            fontsize=VALUE_FONT_SIZE,
            color=FONT_COLOR,
            weight="bold",
        )
        fig.text(
            0.5,
            0.35,
            classification,
            ha="center",
            va="center",
            fontsize=CLASSIFICATION_FONT_SIZE,
            color=FONT_COLOR,
        )

        # Сохраняем изображение в буфер в памяти
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=DPI, transparent=True)
        buf.seek(0)

        return buf.read()

    finally:
        # Гарантируем, что фигура будет закрыта, чтобы избежать утечек памяти
        if fig:
            plt.close(fig)
