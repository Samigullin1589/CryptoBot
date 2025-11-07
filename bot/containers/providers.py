# bot/containers/providers.py
from dependency_injector import providers

from bot.config.settings import settings


def create_service_providers():
    return {
        'ai_content_service': providers.Singleton(
            lambda: __import__('bot.services.ai_content_service', fromlist=['AIContentService']).AIContentService(),
        ),
        
        'image_vision_service': providers.Singleton(
            lambda ai_service: __import__('bot.services.image_vision_service', fromlist=['ImageVisionService']).ImageVisionService(
                ai_service=ai_service
            ),
            ai_service=lambda container: container.ai_content_service(),
        ),
        
        'admin_service': providers.Factory(
            lambda redis_client, bot_instance: __import__('bot.services.admin_service', fromlist=['AdminService']).AdminService(
                redis_client=redis_client,
                bot=bot_instance
            ),
            redis_client=lambda container: container.redis_client(),
            bot_instance=lambda container: container.bot(),
        ),
        
        'user_service': providers.Factory(
            lambda redis_client: __import__('bot.services.user_service', fromlist=['UserService']).UserService(
                redis_client=redis_client
            ),
            redis_client=lambda container: container.redis_client(),
        ),
        
        'market_data_service': providers.Factory(
            lambda http_client: __import__('bot.services.market_data_service', fromlist=['MarketDataService']).MarketDataService(
                http_client=http_client
            ),
            http_client=lambda container: container.http_client(),
        ),
        
        'parser_service': providers.Factory(
            lambda http_client: __import__('bot.services.parser_service', fromlist=['ParserService']).ParserService(
                http_client=http_client
            ),
            http_client=lambda container: container.http_client(),
        ),
        
        'news_service': providers.Factory(
            lambda redis_client, http_client: __import__('bot.services.news_service', fromlist=['NewsService']).NewsService(
                redis_client=redis_client,
                http_client=http_client
            ),
            redis_client=lambda container: container.redis_client(),
            http_client=lambda container: container.http_client(),
        ),
        
        'moderation_service': providers.Factory(
            lambda redis_client, bot_instance: __import__('bot.services.moderation_service', fromlist=['ModerationService']).ModerationService(
                redis_client=redis_client,
                bot=bot_instance
            ),
            redis_client=lambda container: container.redis_client(),
            bot_instance=lambda container: container.bot(),
        ),
        
        'coin_list_service': providers.Factory(
            lambda redis_client, http_client: __import__('bot.services.coin_list_service', fromlist=['CoinListService']).CoinListService(
                redis_client=redis_client,
                http_client=http_client,
                config=settings.coin_list_service
            ),
            redis_client=lambda container: container.redis_client(),
            http_client=lambda container: container.http_client(),
        ),
        
        'verification_service': providers.Factory(
            lambda user_service: __import__('bot.services.verification_service', fromlist=['VerificationService']).VerificationService(
                user_service=user_service
            ),
            user_service=lambda container: container.user_service(),
        ),
        
        'price_service': providers.Factory(
            lambda redis_client, market_data_service: __import__('bot.services.price_service', fromlist=['PriceService']).PriceService(
                redis_client=redis_client,
                market_data_service=market_data_service,
                config=settings.price_service
            ),
            redis_client=lambda container: container.redis_client(),
            market_data_service=lambda container: container.market_data_service(),
        ),
        
        'achievement_service': providers.Factory(
            lambda market_data_service, redis_client: __import__('bot.services.achievement_service', fromlist=['AchievementService']).AchievementService(
                market_data_service=market_data_service,
                redis_client=redis_client
            ),
            market_data_service=lambda container: container.market_data_service(),
            redis_client=lambda container: container.redis_client(),
        ),
        
        'mining_service': providers.Factory(
            lambda market_data_service: __import__('bot.services.mining_service', fromlist=['MiningService']).MiningService(
                market_data_service=market_data_service
            ),
            market_data_service=lambda container: container.market_data_service(),
        ),
        
        'asic_service': providers.Factory(
            lambda parser_service, redis_client: __import__('bot.services.asic_service', fromlist=['AsicService']).AsicService(
                parser_service=parser_service,
                redis_client=redis_client
            ),
            parser_service=lambda container: container.parser_service(),
            redis_client=lambda container: container.redis_client(),
        ),
        
        'crypto_center_service': providers.Factory(
            lambda ai_service, news_service, redis_client: __import__('bot.services.crypto_center_service', fromlist=['CryptoCenterService']).CryptoCenterService(
                ai_service=ai_service,
                news_service=news_service,
                redis_client=redis_client
            ),
            ai_service=lambda container: container.ai_content_service(),
            news_service=lambda container: container.news_service(),
            redis_client=lambda container: container.redis_client(),
        ),
        
        'security_service': providers.Factory(
            lambda ai_content_service, image_vision_service, moderation_service, redis_client, bot_instance: __import__('bot.services.security_service', fromlist=['SecurityService']).SecurityService(
                ai_content_service=ai_content_service,
                image_vision_service=image_vision_service,
                moderation_service=moderation_service,
                redis_client=redis_client,
                bot=bot_instance
            ),
            ai_content_service=lambda container: container.ai_content_service(),
            image_vision_service=lambda container: container.image_vision_service(),
            moderation_service=lambda container: container.moderation_service(),
            redis_client=lambda container: container.redis_client(),
            bot_instance=lambda container: container.bot(),
        ),
        
        'mining_game_service': providers.Factory(
            lambda asic_service, achievement_service, user_service, redis_client: __import__('bot.services.mining_game_service', fromlist=['MiningGameService']).MiningGameService(
                asic_service=asic_service,
                achievement_service=achievement_service,
                user_service=user_service,
                redis_client=redis_client
            ),
            asic_service=lambda container: container.asic_service(),
            achievement_service=lambda container: container.achievement_service(),
            user_service=lambda container: container.user_service(),
            redis_client=lambda container: container.redis_client(),
        ),
        
        'quiz_service': providers.Factory(
            lambda ai_content_service: __import__('bot.services.quiz_service', fromlist=['QuizService']).QuizService(
                ai_content_service=ai_content_service
            ),
            ai_content_service=lambda container: container.ai_content_service(),
        ),
    }