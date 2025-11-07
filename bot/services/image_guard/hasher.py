# bot/services/image_guard/hasher.py
"""
Перцептивное хэширование изображений.
"""
from PIL import Image, ImageOps
from loguru import logger


class ImageHasher:
    """
    Компонент для вычисления перцептивных хэшей изображений.
    
    Использует алгоритм dHash (difference hash) для создания
    устойчивых к изменениям хэшей изображений.
    
    Алгоритм dHash:
    1. Преобразование в grayscale
    2. Уменьшение до 9x8 пикселей
    3. Сравнение соседних пикселей
    4. Создание 64-битного хэша
    """
    
    # Константы
    HASH_SIZE = 8
    HASH_WIDTH = 9
    
    @staticmethod
    def compute_dhash(image: Image.Image) -> int:
        """
        Вычисляет 64-битный перцептивный dHash.
        
        Args:
            image: PIL изображение
            
        Returns:
            64-битный хэш изображения
        """
        try:
            # Применяем EXIF ротацию если есть
            img = ImageOps.exif_transpose(image)
            
            # Конвертируем в grayscale
            img = img.convert("L")
            
            # Уменьшаем до 9x8
            img = img.resize(
                (ImageHasher.HASH_WIDTH, ImageHasher.HASH_SIZE),
                Image.Resampling.LANCZOS
            )
            
            # Получаем пиксели
            pixels = list(img.getdata())
            
            # Вычисляем хэш
            hash_val = 0
            
            for row in range(ImageHasher.HASH_SIZE):
                for col in range(ImageHasher.HASH_SIZE):
                    # Индексы для текущего и следующего пикселя
                    left_idx = row * ImageHasher.HASH_WIDTH + col
                    right_idx = row * ImageHasher.HASH_WIDTH + col + 1
                    
                    left_pixel = pixels[left_idx]
                    right_pixel = pixels[right_idx]
                    
                    # Сдвигаем и добавляем бит
                    hash_val = (hash_val << 1) | (1 if left_pixel > right_pixel else 0)
            
            logger.debug(f"🔢 Вычислен dHash: {hash_val}")
            return hash_val
            
        except Exception as e:
            logger.error(f"❌ Ошибка вычисления dHash: {e}", exc_info=True)
            raise
    
    @staticmethod
    def hamming_distance(hash1: int, hash2: int) -> int:
        """
        Вычисляет расстояние Хэмминга между двумя хэшами.
        
        Расстояние Хэмминга - количество битов, в которых
        два числа различаются.
        
        Args:
            hash1: Первый хэш
            hash2: Второй хэш
            
        Returns:
            Количество различающихся битов (0-64)
        """
        # XOR выделяет различающиеся биты
        # bit_count() считает количество единиц
        xor_result = hash1 ^ hash2
        distance = xor_result.bit_count()
        
        return distance
    
    @staticmethod
    def similarity_percent(hash1: int, hash2: int) -> float:
        """
        Вычисляет процент схожести между хэшами.
        
        Args:
            hash1: Первый хэш
            hash2: Второй хэш
            
        Returns:
            Процент схожести (0.0-100.0)
        """
        distance = ImageHasher.hamming_distance(hash1, hash2)
        total_bits = 64
        
        similarity = ((total_bits - distance) / total_bits) * 100
        
        return similarity