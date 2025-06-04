package com.example;

import javax.persistence.Entity;
import javax.persistence.Id;
import javax.validation.Valid;
import javax.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

@RestController
public class TestController {
    
    @GetMapping("/test")
    public String test(HttpServletRequest request) {
        return "Hello Spring 5!";
    }
    
    @PostMapping("/user")
    public String createUser(@Valid @RequestBody User user) {
        return "User created: " + user.getName();
    }
}

@Entity
class User {
    @Id
    private Long id;
    private String name;
    
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
} 