# bot/services/advanced_security/inspectors/domain_inspector.py
"""
Инспектор для анализа доменов в ссылках.
"""
import re
from typing import List
from urllib.parse import urlparse

from loguru import logger

from bot.services.advanced_security.inspectors.base import BaseInspector
from bot.services.advanced_security.models import InspectionResult


# Регулярное выражение для URL
URL_PATTERN = re.compile(
    r"https?://[^\s/$.?#].[^\s]*",
    re.IGNORECASE
)


class DomainInspector(BaseInspector):
    """
    Инспектор доменов.
    
    Извлекает и анализирует домены из ссылок на:
    - Присутствие в черном списке (через learning service)
    - Подозрительные TLD
    - Безопасные домены
    """
    
    def __init__(self, config, learning_service):
        """
        Инициализация инспектора доменов.
        
        Args:
            config: Конфигурация безопасности
            learning_service: Сервис обучения для проверки черного списка
        """
        super().__init__(config)
        self.learning_service = learning_service
    
    async def inspect(self, text: str) -> InspectionResult:
        """
        Анализирует домены в тексте.
        
        Args:
            text: Текст с потенциальными ссылками
            
        Returns:
            Результат проверки с найденными доменами
        """
        result = InspectionResult()
        
        if not text:
            return result
        
        # Извлекаем домены
        domains = self._extract_domains(text)
        
        if not domains:
            return result
        
        result.metadata["domains"] = domains
        
        # Проверяем каждый домен
        for domain in domains:
            await self._check_domain(domain, result)
        
        if result.score > 0:
            logger.info(
                f"DomainInspector: score={result.score}, "
                f"domains={domains}, reasons={result.reasons}"
            )
        
        return result
    
    def _extract_domains(self, text: str) -> List[str]:
        """
        Извлекает домены из URL в тексте.
        
        Args:
            text: Текст для анализа
            
        Returns:
            Список уникальных доменов
        """
        domains = set()
        
        for match in URL_PATTERN.finditer(text):
            try:
                url = match.group(0)
                parsed = urlparse(url)
                hostname = parsed.hostname
                
                if hostname:
                    hostname_lower = hostname.lower()
                    
                    # Пропускаем безопасные домены
                    if hostname_lower not in self.config.SAFE_DOMAINS:
                        domains.add(hostname_lower)
            except Exception as e:
                logger.debug(f"Ошибка парсинга URL '{url}': {e}")
                continue
        
        return list(domains)
    
    async def _check_domain(
        self,
        domain: str,
        result: InspectionResult
    ) -> None:
        """
        Проверяет один домен на различные признаки угрозы.
        
        Args:
            domain: Доменное имя
            result: Результат для добавления оценок
        """
        # Проверка в черном списке через learning service
        is_blacklisted = await self.learning_service.is_bad_domain(domain)
        
        if is_blacklisted:
            result.add_reason(
                f"blacklisted_domain:{domain}",
                self.config.BAD_DOMAIN_SCORE
            )
            result.metadata["blacklisted_domains"] = \
                result.metadata.get("blacklisted_domains", []) + [domain]
            return  # Один плохой домен достаточен
        
        # Проверка подозрительных TLD
        if self._has_suspicious_tld(domain):
            result.add_reason(
                f"suspicious_tld:{domain}",
                self.config.SUSPICIOUS_TLD_SCORE
            )
            result.metadata["suspicious_tld_domains"] = \
                result.metadata.get("suspicious_tld_domains", []) + [domain]
    
    def _has_suspicious_tld(self, domain: str) -> bool:
        """
        Проверяет, имеет ли домен подозрительный TLD.
        
        Args:
            domain: Доменное имя
            
        Returns:
            True если TLD подозрительный
        """
        return any(
            domain.endswith(tld)
            for tld in self.config.SUSPICIOUS_TLDS
        )