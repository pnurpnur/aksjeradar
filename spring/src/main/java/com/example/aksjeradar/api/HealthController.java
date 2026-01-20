package com.example.aksjeradar.api;

import com.example.aksjeradar.service.MarketDataService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {
  private final MarketDataService service;
  public HealthController(MarketDataService service) { this.service = service; }

  @GetMapping("/health")
  public String health() { return "ok"; }

  @GetMapping("/run")
  public String runNow() {
    new Thread(() -> service.updateDatabase()).start();
    return "Triggered";
  }
}
