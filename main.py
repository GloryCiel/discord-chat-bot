"""
Main entry point for the Discord bot
"""
import asyncio
from src.bot.bot import DiscordBot
from src.config.settings import Settings
from src.utils.logger import setup_logger

async def main():
    # Set up logging
    logger = setup_logger("discord_bot")
    
    try:
        # Load settings
        settings = Settings()
        settings.validate()
        
        # Initialize and run bot
        bot = DiscordBot(settings=settings)
        logger.info("Starting bot...")
        await bot.start(settings.discord_token)
        
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 
