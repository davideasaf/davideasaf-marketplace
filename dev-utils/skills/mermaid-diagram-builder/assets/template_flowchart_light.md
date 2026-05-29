# Flowchart Template - Light Theme

This is a template for creating flowcharts with light theme styling.

```mermaid
%%{init: {'theme':'default', 'themeVariables': { 'primaryColor':'#E8EAF6', 'primaryTextColor':'#000', 'primaryBorderColor':'#7986CB', 'lineColor':'#666', 'secondaryColor':'#C5E1A5', 'tertiaryColor':'#FFE082'}}}%%

flowchart TD
    classDef statusNode fill:#BBDEFB,stroke:#1976D2,stroke-width:2px,color:#000
    classDef actionNode fill:#E1BEE7,stroke:#7B1FA2,stroke-width:2px,color:#000
    classDef decisionNode fill:#FFF9C4,stroke:#F57C00,stroke-width:2px,color:#000
    classDef successNode fill:#C8E6C9,stroke:#388E3C,stroke-width:2px,color:#000
    classDef warningNode fill:#FFE0B2,stroke:#E65100,stroke-width:2px,color:#000
    classDef errorNode fill:#FFCDD2,stroke:#C62828,stroke-width:2px,color:#000
    classDef defaultNode fill:#F5F5F5,stroke:#616161,stroke-width:2px,color:#000

    %% Define your nodes here
    Start([Start]):::defaultNode
    Step1[Process Step]:::actionNode
    Decision{Question?}:::decisionNode
    Success([Success]):::successNode
    Error([Error]):::errorNode

    %% Define your connections here
    Start --> Step1
    Step1 --> Decision
    Decision -->|Yes| Success
    Decision -->|No| Error
```

## Usage

1. Copy the template above
2. Modify node definitions to match your workflow
3. Update connections between nodes
4. Adjust class applications (:::className) as needed
5. Keep text concise (under 60 characters per node)
