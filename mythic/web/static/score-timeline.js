import Login from './login.js'
import Menu from './menu.js'

export default {
    data() {
        return {
            'characterName': '',
            'server': '',
            'servers': {},
            'serverNames': [],
            'showOption': true,
            'showDungeons': '0',
            'graph2d': null,
            'graphs': {
                '1': {
                    'items': [],
                    'groups': [{
                        id: '0',
                        content: "total",
                        options: {
                            excludeFromStacking: true
                        }
                    }],
                    'options': {
                        style: 'bar',
                        stack: true,
                        legend: true,
                        locale: 'en',
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
                            left: { range: { min: 0, max: 0 } }
                        },
                        height: 900
                    }
                },
                '0': {
                    'items': [],
                    'groups': [{
                        id: '0',
                        content: "total",
                        options: {
                            excludeFromStacking: true
                        }
                    }],
                    'options': {
                        style: 'bar',
                        stack: false,
                        legend: false,
                        locale: 'en',
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
                            left: { range: { min: 0, max: 0 } }
                        },
                        height: 900
                    }
                }
            }
        }
    },
    components: {
        Login, Menu
    },
    watch: {
        showDungeons(newVal, oldVal) {
            if (this.graph2d == null) {
                return;
            }
            const g = this.graphs[this.showDungeons];
            this.graph2d.setItems(g.items);
            this.graph2d.setGroups(g.groups);
            this.graph2d.setOptions(g.options);
        }
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
                
                let season = 0;
                let period = 0;
                let dungeonScore = {};
                let minTimestamp = 0;
                let maxTimestamp = 0;
                let periodTimestamp = 0;
                const oneWeek = 7*24*3600*1000;

                this.graphs['1'].items = [];
                this.graphs['1'].groups = [{
                    id: '0',
                    content: "total",
                    options: {
                        excludeFromStacking: true
                    }
                }];
                this.graphs['0'].items = [];
                const items1 = this.graphs['1'].items;
                const groups = this.graphs['1'].groups;
                const items2 = this.graphs['0'].items;

                const addSummary = () => {
                    let score = 0
                    for (let did in dungeonScore) {
                        const arr = dungeonScore[did]
                        const dscore = Math.max(arr[0], arr[1]) * 1.5 + Math.min(arr[0], arr[1]) * 0.5
                        score += dscore

                        const dname = groups.find(g => g.id == String(did)).content

                        items1.push({
                            x: periodTimestamp,
                            y: dscore,
                            end: periodTimestamp + oneWeek,
                            group: String(did),
                            label: {
                                content: String(Math.round(dscore)) + '(' + dname.substring(0, 1) + ')',
                                xOffset: 0,
                                yOffset: 20
                            }
                        })
                    }
                    if (score > 0) {
                        items1.push({
                            x: periodTimestamp,
                            y: score,
                            end: periodTimestamp + oneWeek,
                            group: '0',
                            label: {
                                content: String(Math.round(score)),
                                xOffset: 0,
                                yOffset: -20
                            }
                        })
                        items2.push({
                            x: periodTimestamp,
                            y: score,
                            end: periodTimestamp + oneWeek,
                            group: '0',
                            label: {
                                content: String(Math.round(score)),
                                xOffset: 0,
                                yOffset: -20
                            }
                        })
                    }
                }
                
                data.forEach(data => {
                    if (data.season != season) {
                        dungeonScore = {};
                        season = data.season;
                        period = 0;
                    }
                    if (data.period != period) {
                        if (minTimestamp == 0) {
                            minTimestamp = data.timestamp;
                        } else {
                            while (period < data.period) {
                                addSummary();
                                period++;
                                periodTimestamp += oneWeek;
                            }
                        }
                        period = data.period
                        periodTimestamp = data.timestamp
                        maxTimestamp = data.timestamp
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
                if (items1.length >= 0) {
                    const timelineMargin = oneWeek;
                    const container = document.getElementById('timeline');
                    container.innerHTML = '';
                    const g = this.graphs[this.showDungeons];

                    const xRangeMin = minTimestamp - timelineMargin;
                    const xRangeMax = maxTimestamp + timelineMargin * 2;
                    const yRangeMax = Math.ceil(Math.max.apply(null, items1.filter(it => it.group == '0').map(it => it.y)) / 100) * 100 + 200;

                    this.graphs['0'].options.min = xRangeMin;
                    this.graphs['0'].options.max = xRangeMax;
                    this.graphs['0'].options.dataAxis.left.range.max = yRangeMax;
                    this.graphs['1'].options.min = xRangeMin;
                    this.graphs['1'].options.max = xRangeMax;
                    this.graphs['1'].options.dataAxis.left.range.max = yRangeMax;

                    this.graph2d = new vis.Graph2d(container, g.items, g.groups, g.options);
                    this.graph2d.setWindow(xRangeMin, xRangeMax);
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
            for (let key in this.servers) {
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
            <v-text-field type="text" label="캐릭터명" v-model="characterName" />
        </v-col>
        <v-col cols="12" sm="6">
            <v-combobox id="server" label="서버" :items="serverNames" v-model="server" />
        </v-col>
    </v-row>
    <v-row no-gutters>
        <v-col>
            <v-btn class="ma-1" variant="outlined" @click="search">검색</v-btn>
            <v-btn class="ma-1" variant="outlined" @click="showOption=!showOption">{{ showOption ? "검색 조건 닫기" : "검색 조건 열기" }}</v-btn>
            <Menu/>
            <Login/>
            <v-btn-toggle class="ma-1" v-model="showDungeons" mandatory>
                <v-btn class="pa-1" variant="outlined" value="0">총점만 표시</v-btn>
                <v-btn class="pa-1" variant="outlined" value="1">던전별 표시</v-btn>
            </v-btn-toggle>
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
