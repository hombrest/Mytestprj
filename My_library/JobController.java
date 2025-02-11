package com.example.controller;

import com.example.service.JobScraperService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.concurrent.CompletableFuture;


@RestController
@RequestMapping("/")
public class JobController {

    private final JobScraperService jobScraperService;

    @Autowired
    public JobController(JobScraperService jobScraperService) {
        this.jobScraperService = jobScraperService;
    }

    @GetMapping("/scrape")
    public CompletableFuture<String> scrapeJobs() {
        return jobScraperService.scrapeJobs();
    }
}
