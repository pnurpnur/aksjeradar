package com.example.aksjeradar.model;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import lombok.Data;

@Data
@Entity
@Table(name = "stock_data")
public class StockData {
  @Id
  private String ticker;

  private OffsetDateTime timestamp;

  private Double pe;
  private Double pb;
  private Double debtToEquity;
  private BigDecimal dividendYield;
  private Double mom1d;
  private Double mom1y;
  private Double mom1m;
  private Double mom3m;
  private Double price;
  private Double target;
  private Double targetLow;
  private Double targetHigh;
  private Double marketcap;
  private String name;

  // getters/setters
  // (for brevity: generate via IDE or Lombok in real repo)
}
