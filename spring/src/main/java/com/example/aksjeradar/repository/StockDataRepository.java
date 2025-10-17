package com.example.aksjeradar.repository;

import com.example.aksjeradar.model.StockData;
import org.springframework.data.jpa.repository.JpaRepository;

public interface StockDataRepository extends JpaRepository<StockData, String> {
}
