package com.example.aksjeradar.scheduler;

import com.example.aksjeradar.service.MarketDataService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class UpdateScheduler {
  private final Logger logger = LoggerFactory.getLogger(UpdateScheduler.class);
  private final MarketDataService service;

  public UpdateScheduler(MarketDataService service) {
    this.service = service;
  }

  @Scheduled(cron = "0 0 9 * * *", zone = "Europe/Oslo")
  public void runDaily() {
    logger.info("Starting daily update...");
    service.updateDatabase();
  }
}
