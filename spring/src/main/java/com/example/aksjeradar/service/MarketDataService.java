package com.example.aksjeradar.service;

import com.example.aksjeradar.model.StockData;
import com.example.aksjeradar.repository.StockDataRepository;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.select.Elements;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import yahoofinance.YahooFinance;
import yahoofinance.histquotes.HistoricalQuote;

import java.io.IOException;
import java.math.BigDecimal;
import java.net.http.*;
import java.net.URI;
import java.time.*;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class MarketDataService {
  private final Logger logger = LoggerFactory.getLogger(MarketDataService.class);
  private final StockDataRepository repo;
  private final HttpClient http = HttpClient.newHttpClient();

  public MarketDataService(StockDataRepository repo) {
    this.repo = repo;
  }

  public List<String> getExistingTickers() {
    return repo.findAll().stream().map(s -> s.getTicker()).collect(Collectors.toList());
  }

  public List<String> getTrendingYahoo(String region) {
    String url = "https://query1.finance.yahoo.com/v1/finance/trending/" + region;
    HttpRequest req = HttpRequest.newBuilder(URI.create(url))
        .header("User-Agent", "Java 17 HttpClient")
        .GET()
        .build();
    try {
      HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
      if (resp.statusCode() != 200) {
        logger.warn("Yahoo trending returned status {}", resp.statusCode());
        return Collections.emptyList();
      }
      // crude parse for "symbol" occurrences — simple and resilient
      String body = resp.body();
      Set<String> symbols = new HashSet<>();
      int idx = 0;
      while ((idx = body.indexOf("\"symbol\":\"", idx)) >= 0) {
        idx += 10;
        int end = body.indexOf("\"", idx);
        if (end > idx) {
          String sym = body.substring(idx, end);
          symbols.add(sym);
        } else break;
      }
      return new ArrayList<>(symbols);
    } catch (Exception e) {
      logger.warn("Error fetching Yahoo trending: {}", e.toString());
      return Collections.emptyList();
    }
  }

  public List<String> getFinvizTickers(String category) {
    try {
      String url = "https://finviz.com/screener.ashx?v=111&s=" + category;
      Document doc = Jsoup.connect(url)
          .userAgent("Mozilla/5.0")
          .timeout(10_000)
          .get();
      Elements links = doc.select("a.tab-link");
      List<String> tickers = links.stream()
          .map(e -> e.text().trim())
          .filter(t -> t.matches("^[A-Za-z]+$"))
          .distinct()
          .collect(Collectors.toList());
      logger.info("Finviz {} tickers: {}", category, tickers.size());
      return tickers;
    } catch (IOException e) {
      logger.warn("Finviz fetch error: {}", e.toString());
      return Collections.emptyList();
    }
  }

  public List<String> getAllTickers() {
    List<String> existing = getExistingTickers();
    List<String> yahooUS = getTrendingYahoo("US");
    List<String> yahooCA = getTrendingYahoo("CA");
    List<String> yahooGB = getTrendingYahoo("GB");
    List<String> fvTop = getFinvizTickers("ta_topgainers");
    List<String> fvActive = getFinvizTickers("ta_mostactive");

    Set<String> all = new HashSet<>();
    all.addAll(existing);
    all.addAll(yahooUS);
    all.addAll(yahooCA);
    all.addAll(yahooGB);
    all.addAll(fvTop);
    all.addAll(fvActive);

    List<String> filtered = all.stream()
        .filter(s -> s.matches("^[A-Za-z]+$"))
        .collect(Collectors.toList());

    logger.info("Total tickers: {}", filtered.size());
    return filtered;
  }

  private Double percentChange(List<HistoricalQuote> hist, int days) {
    if (hist.size() < days + 1) return null;
    try {
      BigDecimal latest = hist.get(hist.size() - 1).getClose();
      BigDecimal old = hist.get(hist.size() - (days + 1)).getClose();
      if (latest == null || old == null) return null;
      double l = latest.doubleValue();
      double o = old.doubleValue();
      if (o == 0) return null;
      return ((l - o) / o) * 100.0;
    } catch (Exception e) {
      return null;
    }
  }

  public void updateDatabase() {
    List<String> tickers = getAllTickers();
    for (String t : tickers) {
      try {
        yahoofinance.Stock s = YahooFinance.get(t);
        if (s == null || s.getQuote() == null || s.getQuote().getPrice() == null) {
          logger.info("No price for {}", t);
          continue;
        }

        // historical (last ~2 years)
        Calendar from = Calendar.getInstance();
        from.add(Calendar.YEAR, -2);
        List<HistoricalQuote> hist = s.getHistory(from, java.util.Calendar.getInstance(), yahoofinance.histquotes.Interval.DAILY);

        if (hist == null || hist.isEmpty()) {
          logger.info("No history for {}", t);
          continue;
        }

        Double price = s.getQuote().getPrice().doubleValue();
        Double mom1d = percentChange(hist, 1);
        Double mom1m = percentChange(hist, 22);
        Double mom3m = percentChange(hist, 66);
        Double mom1y = percentChange(hist, 252);

        StockData sd = new StockData();
        sd.setTicker(t);
        sd.setTimestamp(OffsetDateTime.now(ZoneOffset.UTC));
        sd.setPrice(price);

        // info fields (attempt to map)
        sd.setPe(s.getStats() != null && s.getStats().getPe() != null ? s.getStats().getPe().doubleValue() : null);
        sd.setPb(null);
        sd.setDebtToEquity(null);
        sd.setDividendYield(s.getDividend() != null && s.getDividend().getAnnualYieldPercent() != null ? s.getDividend().getAnnualYieldPercent() : null);

        sd.setMom1d(mom1d);
        sd.setMom1m(mom1m);
        sd.setMom3m(mom3m);
        sd.setMom1y(mom1y);

        sd.setTarget(null);
        sd.setTargetLow(null);
        sd.setTargetHigh(null);
        sd.setMarketcap(s.getStats() != null && s.getStats().getMarketCap() != null ? s.getStats().getMarketCap().doubleValue() : null);
        sd.setName(s.getName());

        repo.save(sd);
        logger.info("Updated {}", t);
      } catch (Exception e) {
        logger.warn("Error updating {} : {}", t, e.toString());
      }
    }
    logger.info("Finished updating database.");
  }
}
