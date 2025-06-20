import io
import matplotlib.pyplot as plt

def generate_fng_image(value: int, classification: str) -> bytes:
    """
    Создает изображение для Индекса страха и жадности.
    Эта функция является синхронной и блокирующей.
    """
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8, 4.5), subplot_kw={'projection': 'polar'})
    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.grid(False)
    ax.spines['polar'].set_visible(False)
    ax.set_ylim(0, 1)

    colors = ['#d94b4b', '#e88452', '#ece36a', '#b7d968', '#73c269']
    for i in range(100):
        ax.barh(1, 0.0314, left=3.14 - (i * 0.0314), height=0.3, color=colors[min(4, int(i / 25))])

    angle = 3.14 - (value * 0.0314)
    ax.annotate('', xy=(angle, 1), xytext=(0, 0), arrowprops=dict(facecolor='white', shrink=0.05, width=4, headwidth=10))

    fig.text(0.5, 0.5, f"{value}", ha='center', va='center', fontsize=48, color='white', weight='bold')
    fig.text(0.5, 0.35, classification, ha='center', va='center', fontsize=20, color='white')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, transparent=True)
    buf.seek(0)
    plt.close(fig)

    return buf.read()