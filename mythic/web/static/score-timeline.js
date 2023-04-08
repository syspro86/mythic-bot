import Login from './login.js'

export default {
    data() {
        return {
            'characterName': '',
            'server': '',
            'servers': {},
            'serverNames': [],
            'showOption': true,
        }
    },
    components: {
        Login
    },
    methods: {
        search() {
            if (this.characterName == '') {
                return;
            }
            this.characterName = this.characterName.substring(0, 1).toUpperCase() +
                this.characterName.substring(1).toLowerCase();
            
            if (window.localStorage) {
                window.localStorage.setItem('relation_server', this.server);
                window.localStorage.setItem('relation_character', this.characterName);
            }

            fetch('char/mythic_rating/' + encodeURI(this.server) + '/' + encodeURI(this.characterName)).then(async resp => {
                const data = await resp.json();
                
                let period = 0
                let dungeonScore = {}
                let minPeriod = 0
                let maxPeriod = 0

                let items = []
                let groups = [{
                    id: '0',
                    content: "total",
                    options: {
                        excludeFromStacking: true
                    }
                }]

                const addSummary = () => {
                    let score = 0
                    for (let did in dungeonScore) {
                        const arr = dungeonScore[did]
                        const dscore = Math.max(arr[0], arr[1]) * 1.5 + Math.min(arr[0], arr[1]) * 0.5
                        score += dscore

                        items.push({
                            x: period,
                            y: dscore,
                            group: String(did),
                            label: {
                                content: String(parseInt(dscore)),
                                xOffset: -15,
                                yOffset: 20
                            }
                        })
                    }
                    if (score > 0) {
                        items.push({
                            x: period,
                            y: score,
                            group: '0',
                            label: {
                                content: String(parseInt(score)),
                                xOffset: -20,
                                yOffset: -20
                            }
                        })
                    }
                }

                
                data.forEach(data => {
                    if (data.period != period) {
                        if (period == 0) {
                            minPeriod = data.period
                        } else {
                            addSummary()
                        }
                        period = data.period
                        maxPeriod = period
                    }
                    if (!dungeonScore[data.dungeon_id]) {
                        dungeonScore[data.dungeon_id] = [0, 0]
                    }
                    dungeonScore[data.dungeon_id][period % 2] = Math.max(dungeonScore[data.dungeon_id][period % 2], data.mythic_rating)
                    if (!(groups.some(g => g.id == String(data.dungeon_id)))) {
                        groups.push({
                            id: String(data.dungeon_id),
                            content: data.dungeon_name
                        })
                    }
                })
                addSummary()
                if (items.length >= 0) {
                    var container = document.getElementById('timeline')
                    container.innerHTML = ''
                    graph2d = new vis.Graph2d(container, items, groups, {
                        style: 'bar',
                        stack: true,
                        legend: true,
                        min: minPeriod - 1,
                        max: maxPeriod + 1,
                        start: minPeriod - 1,
                        end: maxPeriod + 1,
                        // zoomable: false,
                        // barChart: { width: 50, align: 'center' },
                        drawPoints: {
                            onRender: function(item, group, grap2d) {
                                return item.label != null;
                            },
                            style: 'circle'
                        },                        
                        dataAxis: {
                            icons: true,
                            left: {
                                range: {
                                    min: 0,
                                    max: Math.ceil(Math.max.apply(null, items.filter(it => it.group == '0').map(it => it.y)) / 100) * 100 + 200
                                }
                            }
                        },
                        height: 900
                    })
                }
            })
        },
    },
    beforeMount() {
        if (window.localStorage) {
            const server = window.localStorage.getItem('relation_server')
            const run = parseInt(window.localStorage.getItem('relation_run'))
            this.server = server
            this.characterName = window.localStorage.getItem('relation_character')
            if (run > 0) {
                this.minimumRun = run
            }
        }
    },
    mounted() {
        fetch('form/realms').then(async resp => {
            this.servers = await resp.json()
            for (var key in this.servers) {
                this.serverNames.push(this.servers[key]);
            }
            if (this.server == '') {
                this.server = this.serverNames[0]['value']
            }
        })
    },
    template: `
    <v-container fluid>
    <v-row v-if="showOption" no-gutters>
        <v-col cols="12" sm="6">
            <v-sheet>
            <v-text-field type="text" label="캐릭터명" v-model="characterName" />
            </v-sheet>
        </v-col>
        <v-col cols="12" sm="6">
            <v-sheet>
            <v-combobox id="server" label="서버" :items="serverNames" v-model="server" />
            </v-sheet>
        </v-col>
    </v-row>
    <v-row no-gutters>
        <v-col>
            <v-sheet>
            <v-btn class="ma-1" variant="outlined" @click="search">검색</v-btn>
            <v-btn class="ma-1" variant="outlined" @click="showOption=!showOption">{{ showOption ? "검색 조건 닫기" : "검색 조건 열기" }}</v-btn>
            <Login/>
            </v-sheet>
        </v-col>
    </v-row>
    <v-row no-gutters>
        <v-col>
            <div id="timeline"></div>
        </v-col>
    </v-row>
    </v-container>
    `,
};
